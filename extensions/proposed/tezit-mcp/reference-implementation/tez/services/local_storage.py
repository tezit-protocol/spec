"""Local filesystem storage for tezit bundles.

Replaces the S3-backed ``StorageService`` with encrypted local file
storage. Each tezit's files are individually encrypted with AES-256-GCM
and stored under ``{data_dir}/bundles/{tez_id}/``.

Disk layout::

    {data_dir}/bundles/{tez_id}/
        manifest.json     # encrypted file manifest (plaintext JSON)
        file_0.enc        # encrypted file content
        file_1.enc        # encrypted file content
        ...

The ``manifest.json`` is a plaintext JSON index mapping original
filenames to their encrypted file indices, nonces, and tags. It is
NOT itself encrypted -- it contains no sensitive content, only the
structural mapping needed to locate and decrypt individual files.

Quota enforcement is per-``data_dir`` and checked before writes.
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tez.crypto import decrypt_file, encrypt_file

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating encrypted files on disk.

    Attributes:
        success: True if all expected files are present.
        missing: List of original filenames that were not found.
    """

    success: bool
    missing: list[str] = field(default_factory=list)


class LocalStorageService:
    """Encrypted local filesystem storage for tezit bundles.

    Args:
        data_dir: Root directory for all tezit data.
            Bundles are stored under ``{data_dir}/bundles/``.
        quota_gb: Maximum disk usage in gigabytes (default 5.0).
            Set to 0 to disable quota checking.
    """

    def __init__(self, data_dir: str, quota_gb: float = 5.0) -> None:
        self._data_dir = Path(data_dir)
        self._bundles_dir = self._data_dir / "bundles"
        self._quota_bytes = int(quota_gb * 1024 * 1024 * 1024)

        # Ensure the bundles directory exists.
        self._bundles_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def data_dir(self) -> Path:
        """Root data directory."""
        return self._data_dir

    @property
    def bundles_dir(self) -> Path:
        """Directory containing all tezit bundle subdirectories."""
        return self._bundles_dir

    # ------------------------------------------------------------------
    # Store files (encrypt + write)
    # ------------------------------------------------------------------

    def store_files(
        self,
        tez_id: str,
        files: list[dict[str, Any]],
        key: bytes,
    ) -> list[dict[str, Any]]:
        """Encrypt and store files for a tezit bundle.

        Each file in ``files`` must have:
        - ``name``: original filename (str)
        - ``content``: raw file bytes (bytes)
        - ``content_type``: MIME type (str, preserved in manifest)
        - ``size``: original size in bytes (int)

        Files are encrypted individually and written to numbered
        ``.enc`` files. A ``manifest.json`` is written alongside them
        to map original names back to encrypted files.

        Args:
            tez_id: The tezit identifier.
            files: List of file dicts with content to store.
            key: 32-byte AES-256 encryption key.

        Returns:
            List of file metadata dicts (without ``content``) suitable
            for storing in the metadata database. Each dict includes:
            ``name``, ``content_type``, ``size`` (original),
            ``encrypted_size``, and ``index`` (position in bundle).

        Raises:
            OSError: If disk write fails.
            ValueError: If quota would be exceeded.
        """
        bundle_dir = self._bundles_dir / tez_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Pre-check quota (rough estimate: encrypted size ~ plaintext size).
        total_incoming = sum(f["size"] for f in files)
        if not self.check_quota(total_incoming):
            shutil.rmtree(bundle_dir, ignore_errors=True)
            msg = (
                f"Quota exceeded: storing {total_incoming} bytes would "
                f"exceed the {self._quota_bytes} byte limit"
            )
            raise ValueError(msg)

        manifest_entries: list[dict[str, Any]] = []
        file_metadata: list[dict[str, Any]] = []

        for idx, f in enumerate(files):
            content: bytes = f["content"]
            ciphertext, nonce, tag = encrypt_file(content, key)

            enc_filename = f"file_{idx}.enc"
            enc_path = bundle_dir / enc_filename
            enc_path.write_bytes(ciphertext)

            manifest_entries.append({
                "index": idx,
                "name": f["name"],
                "content_type": f.get("content_type", "application/octet-stream"),
                "original_size": f["size"],
                "encrypted_size": len(ciphertext),
                "enc_file": enc_filename,
                "nonce": nonce.hex(),
                "tag": tag.hex(),
            })

            file_metadata.append({
                "name": f["name"],
                "content_type": f.get("content_type", "application/octet-stream"),
                "size": f["size"],
                "encrypted_size": len(ciphertext),
                "index": idx,
            })

        # Write the manifest (plaintext JSON -- no secrets here).
        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_entries, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Stored %d files for tez %s (%d bytes total)",
            len(files),
            tez_id,
            total_incoming,
        )
        return file_metadata

    # ------------------------------------------------------------------
    # Retrieve encrypted bundle (tar.gz)
    # ------------------------------------------------------------------

    def get_encrypted_blob(self, tez_id: str) -> bytes:
        """Create a tar.gz archive of the encrypted bundle directory.

        The archive includes all ``.enc`` files and the
        ``manifest.json``. This is the format used for relay fetch --
        the recipient receives the entire encrypted bundle as a single
        blob and decrypts locally.

        Args:
            tez_id: The tezit identifier.

        Returns:
            The tar.gz archive as bytes.

        Raises:
            FileNotFoundError: If the bundle directory does not exist.
        """
        bundle_dir = self._bundles_dir / tez_id
        if not bundle_dir.is_dir():
            msg = f"Bundle directory not found: {bundle_dir}"
            raise FileNotFoundError(msg)

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for entry in sorted(bundle_dir.iterdir()):
                if entry.is_file():
                    tar.add(str(entry), arcname=entry.name)
        buf.seek(0)
        return buf.read()

    # ------------------------------------------------------------------
    # Retrieve single encrypted file
    # ------------------------------------------------------------------

    def get_file_encrypted(self, tez_id: str, filename: str) -> bytes:
        """Return the raw encrypted bytes of a single file.

        Looks up the original filename in the bundle manifest and
        returns the corresponding ``.enc`` file content.

        Args:
            tez_id: The tezit identifier.
            filename: The original filename (before encryption).

        Returns:
            The encrypted file bytes.

        Raises:
            FileNotFoundError: If the bundle or file does not exist.
            KeyError: If the filename is not in the manifest.
        """
        bundle_dir = self._bundles_dir / tez_id
        manifest = self._read_manifest(bundle_dir)

        entry = self._find_manifest_entry(manifest, filename)
        if entry is None:
            msg = f"File '{filename}' not found in manifest for tez {tez_id}"
            raise KeyError(msg)

        enc_path = bundle_dir / entry["enc_file"]
        if not enc_path.is_file():
            msg = f"Encrypted file not found: {enc_path}"
            raise FileNotFoundError(msg)

        return enc_path.read_bytes()

    # ------------------------------------------------------------------
    # Decrypt and retrieve single file
    # ------------------------------------------------------------------

    def decrypt_and_get(
        self,
        tez_id: str,
        filename: str,
        key: bytes,
    ) -> bytes:
        """Decrypt and return the content of a single file.

        Args:
            tez_id: The tezit identifier.
            filename: The original filename.
            key: The 32-byte AES-256 key used during encryption.

        Returns:
            The decrypted file content.

        Raises:
            FileNotFoundError: If the bundle or file does not exist.
            KeyError: If the filename is not in the manifest.
            cryptography.exceptions.InvalidTag: If decryption fails.
        """
        bundle_dir = self._bundles_dir / tez_id
        manifest = self._read_manifest(bundle_dir)

        entry = self._find_manifest_entry(manifest, filename)
        if entry is None:
            msg = f"File '{filename}' not found in manifest for tez {tez_id}"
            raise KeyError(msg)

        enc_path = bundle_dir / entry["enc_file"]
        if not enc_path.is_file():
            msg = f"Encrypted file not found: {enc_path}"
            raise FileNotFoundError(msg)

        ciphertext = enc_path.read_bytes()
        nonce = bytes.fromhex(entry["nonce"])
        tag = bytes.fromhex(entry["tag"])

        return decrypt_file(ciphertext, key, nonce, tag)

    # ------------------------------------------------------------------
    # Upload validation
    # ------------------------------------------------------------------

    def validate_uploads(
        self,
        tez_id: str,
        expected_files: list[dict[str, Any]],
    ) -> ValidationResult:
        """Check that all expected files exist on disk after storage.

        Reads the bundle manifest and verifies that each expected
        original filename has a corresponding encrypted file present.

        Args:
            tez_id: The tezit identifier.
            expected_files: List of file dicts with ``name`` key.

        Returns:
            A ``ValidationResult`` with success flag and any missing
            filenames.
        """
        bundle_dir = self._bundles_dir / tez_id

        if not bundle_dir.is_dir():
            names = [f["name"] for f in expected_files]
            return ValidationResult(success=False, missing=names)

        manifest_path = bundle_dir / "manifest.json"
        if not manifest_path.is_file():
            names = [f["name"] for f in expected_files]
            return ValidationResult(success=False, missing=names)

        manifest = self._read_manifest(bundle_dir)
        manifest_names = {entry["name"] for entry in manifest}

        missing: list[str] = []
        for f in expected_files:
            name = f["name"]
            if name not in manifest_names:
                missing.append(name)
                continue
            # Also verify the .enc file actually exists on disk.
            entry = self._find_manifest_entry(manifest, name)
            if entry is not None:
                enc_path = bundle_dir / entry["enc_file"]
                if not enc_path.is_file():
                    missing.append(name)

        return ValidationResult(
            success=len(missing) == 0,
            missing=missing,
        )

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_tez(self, tez_id: str) -> None:
        """Delete an entire tezit bundle directory.

        Safe to call on nonexistent tez IDs (no-op).

        Args:
            tez_id: The tezit identifier.
        """
        bundle_dir = self._bundles_dir / tez_id
        if bundle_dir.is_dir():
            shutil.rmtree(bundle_dir)
            logger.info("Deleted bundle directory for tez %s", tez_id)

    # ------------------------------------------------------------------
    # Quota management
    # ------------------------------------------------------------------

    def disk_usage_bytes(self) -> int:
        """Calculate total bytes used by all bundles.

        Walks the bundles directory tree and sums file sizes. This is
        an O(n) operation over all stored files -- acceptable for the
        current fleet scale.

        Returns:
            Total bytes used by all bundle files.
        """
        if not self._bundles_dir.is_dir():
            return 0

        total = 0
        for path in self._bundles_dir.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def check_quota(self, additional_bytes: int) -> bool:
        """Check if adding bytes would stay within the disk quota.

        Args:
            additional_bytes: Number of bytes to be added.

        Returns:
            True if the addition is within quota, False otherwise.
            Always returns True if quota is set to 0 (disabled).
        """
        if self._quota_bytes <= 0:
            return True
        current = self.disk_usage_bytes()
        return (current + additional_bytes) <= self._quota_bytes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_manifest(bundle_dir: Path) -> list[dict[str, Any]]:
        """Read and parse the bundle manifest.json.

        Args:
            bundle_dir: Path to the bundle directory.

        Returns:
            List of manifest entry dicts.

        Raises:
            FileNotFoundError: If manifest.json does not exist.
            json.JSONDecodeError: If manifest.json is malformed.
        """
        manifest_path = bundle_dir / "manifest.json"
        if not manifest_path.is_file():
            msg = f"Manifest not found: {manifest_path}"
            raise FileNotFoundError(msg)
        content = manifest_path.read_text(encoding="utf-8")
        entries: list[dict[str, Any]] = json.loads(content)
        return entries

    @staticmethod
    def _find_manifest_entry(
        manifest: list[dict[str, Any]],
        filename: str,
    ) -> dict[str, Any] | None:
        """Find a manifest entry by original filename.

        Args:
            manifest: List of manifest entry dicts.
            filename: The original filename to look up.

        Returns:
            The matching entry dict, or None if not found.
        """
        for entry in manifest:
            if entry["name"] == filename:
                return entry
        return None
