"""HTTP client for communicating with the tezit relay server.

The relay server acts as a trusted intermediary between PA instances
for tezit sharing. It handles:

- **Key escrow**: Stores the AES-256 encryption key (base64-encoded)
  so authorised recipients can decrypt bundles without direct PA-to-PA
  communication.
- **Tez registration**: Records tezit metadata on the relay so other
  PAs can discover and request access.
- **Share notifications**: Propagates share authorisations across the
  fleet.
- **Blob caching**: Optionally caches encrypted bundles for faster
  cross-network downloads.

Authentication uses a shared secret in the ``X-Relay-Auth`` header.
All requests are synchronous (``urllib.request``) to match the
FastMCP synchronous tool model.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests in seconds.
_DEFAULT_TIMEOUT_SECONDS = 30

# Timeout for blob uploads (potentially large payloads).
_UPLOAD_TIMEOUT_SECONDS = 120


class RelayError(Exception):
    """Raised when the relay returns a non-2xx response.

    Attributes:
        status_code: HTTP status code from the relay.
        detail: Error message or body from the response.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Relay error {status_code}: {detail}")


class RelayClient:
    """HTTP client for the tezit relay server.

    All methods are synchronous and raise ``RelayError`` on non-2xx
    responses. Connection errors raise ``urllib.error.URLError``.

    Args:
        relay_url: Base URL of the relay server (no trailing slash).
            Example: ``"https://relay.example.com"``
        auth_secret: Shared secret for the ``X-Relay-Auth`` header.
        timeout: Default request timeout in seconds.
    """

    def __init__(
        self,
        relay_url: str,
        auth_secret: str,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        # Strip trailing slash for consistent URL construction.
        self._base_url = relay_url.rstrip("/")
        self._auth_secret = auth_secret
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Tez registration
    # ------------------------------------------------------------------

    def register_tez(
        self,
        tez_id: str,
        key_b64: str,
        creator: str,
        name: str,
        description: str,
        content_hash: str,
        file_manifest: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Register a new tezit on the relay.

        The relay stores the encryption key in escrow and records the
        tezit metadata so other PAs can discover and request access.

        Args:
            tez_id: The tezit identifier.
            key_b64: Base64url-encoded AES-256 encryption key.
            creator: Creator's email address.
            name: Display name of the tezit.
            description: Tezit description/abstract.
            content_hash: SHA-256 hash of the unencrypted bundle
                (for integrity verification by recipients).
            file_manifest: List of file metadata dicts (name, size,
                content_type).

        Returns:
            The relay's response as a dict (typically includes
            ``status`` and ``tez_id``).

        Raises:
            RelayError: If the relay returns a non-2xx response.
        """
        payload = {
            "tez_id": tez_id,
            "key_b64": key_b64,
            "creator": creator,
            "name": name,
            "description": description,
            "content_hash": content_hash,
            "file_manifest": file_manifest,
        }
        return self._post(f"/tez/register", payload)

    # ------------------------------------------------------------------
    # Sharing
    # ------------------------------------------------------------------

    def share_tez(
        self,
        tez_id: str,
        recipient: str,
        caller: str,
    ) -> dict[str, Any]:
        """Notify the relay that a tezit has been shared.

        The relay records the share authorisation so the recipient's
        PA can request the decryption key.

        Args:
            tez_id: The tezit identifier.
            recipient: Recipient's email address.
            caller: Email of the user performing the share
                (must be the creator).

        Returns:
            The relay's response as a dict.

        Raises:
            RelayError: If the relay returns a non-2xx response.
        """
        payload = {
            "recipient": recipient,
            "caller": caller,
        }
        return self._post(f"/tez/{tez_id}/share", payload)

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_tez(
        self,
        tez_id: str,
        caller: str,
    ) -> dict[str, Any]:
        """Request deletion of a tezit from the relay.

        Removes the relay's copy of the key and metadata. The relay
        may also purge any cached blob.

        Args:
            tez_id: The tezit identifier.
            caller: Email of the user requesting deletion
                (must be the creator).

        Returns:
            The relay's response as a dict.

        Raises:
            RelayError: If the relay returns a non-2xx response.
        """
        return self._delete(f"/tez/{tez_id}", params={"caller": caller})

    # ------------------------------------------------------------------
    # Key retrieval
    # ------------------------------------------------------------------

    def request_key(
        self,
        tez_id: str,
        caller: str,
    ) -> str | None:
        """Request the decryption key for a tezit from the relay.

        The relay checks that the caller is authorised (creator or
        recipient) before releasing the key.

        Args:
            tez_id: The tezit identifier.
            caller: Email of the requesting user.

        Returns:
            The base64url-encoded AES-256 key, or ``None`` if the
            relay does not have the key (tez not registered or
            caller not authorised).

        Raises:
            RelayError: If the relay returns an unexpected error
                (not 404/403).
        """
        try:
            result = self._get(
                f"/tez/{tez_id}/key",
                params={"caller": caller},
            )
            key: str | None = result.get("key_b64")
            return key
        except RelayError as e:
            if e.status_code in (403, 404):
                logger.info(
                    "Key request denied for tez %s (caller=%s): %s",
                    tez_id,
                    caller,
                    e.detail,
                )
                return None
            raise

    # ------------------------------------------------------------------
    # Blob upload
    # ------------------------------------------------------------------

    def upload_blob(
        self,
        tez_id: str,
        blob: bytes,
    ) -> dict[str, Any]:
        """Upload an encrypted bundle blob to the relay cache.

        The relay caches the encrypted bundle so recipients can
        download it without direct PA-to-PA connectivity. The blob
        should be the tar.gz output of
        ``LocalStorageService.get_encrypted_blob``.

        Args:
            tez_id: The tezit identifier.
            blob: The encrypted bundle as bytes (tar.gz archive).

        Returns:
            The relay's response as a dict (typically includes
            ``status`` and ``size``).

        Raises:
            RelayError: If the relay returns a non-2xx response.
        """
        url = f"{self._base_url}/tez/{tez_id}/blob"
        headers = {
            "X-Relay-Auth": self._auth_secret,
            "Content-Type": "application/octet-stream",
        }

        request = urllib.request.Request(
            url,
            data=blob,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=_UPLOAD_TIMEOUT_SECONDS
            ) as response:
                body = response.read().decode("utf-8")
                result: dict[str, Any] = json.loads(body)
                return result
        except urllib.error.HTTPError as e:
            detail = self._read_error_body(e)
            raise RelayError(e.code, detail) from e

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a JSON POST request to the relay.

        Args:
            path: URL path (appended to base_url).
            payload: JSON-serialisable request body.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RelayError: On non-2xx response.
        """
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "X-Relay-Auth": self._auth_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout
            ) as response:
                body = response.read().decode("utf-8")
                result: dict[str, Any] = json.loads(body)
                return result
        except urllib.error.HTTPError as e:
            detail = self._read_error_body(e)
            raise RelayError(e.code, detail) from e

    def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a GET request to the relay.

        Args:
            path: URL path (appended to base_url).
            params: Optional query parameters.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RelayError: On non-2xx response.
        """
        url = f"{self._base_url}{path}"
        if params:
            query = "&".join(
                f"{urllib.request.quote(k)}={urllib.request.quote(v)}"
                for k, v in params.items()
            )
            url = f"{url}?{query}"

        headers = {
            "X-Relay-Auth": self._auth_secret,
            "Accept": "application/json",
        }

        request = urllib.request.Request(
            url,
            headers=headers,
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout
            ) as response:
                body = response.read().decode("utf-8")
                result: dict[str, Any] = json.loads(body)
                return result
        except urllib.error.HTTPError as e:
            detail = self._read_error_body(e)
            raise RelayError(e.code, detail) from e

    def _delete(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a DELETE request to the relay.

        Args:
            path: URL path (appended to base_url).
            params: Optional query parameters.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RelayError: On non-2xx response.
        """
        url = f"{self._base_url}{path}"
        if params:
            query = "&".join(
                f"{urllib.request.quote(k)}={urllib.request.quote(v)}"
                for k, v in params.items()
            )
            url = f"{url}?{query}"

        headers = {
            "X-Relay-Auth": self._auth_secret,
            "Accept": "application/json",
        }

        request = urllib.request.Request(
            url,
            headers=headers,
            method="DELETE",
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout
            ) as response:
                body = response.read().decode("utf-8")
                result: dict[str, Any] = json.loads(body)
                return result
        except urllib.error.HTTPError as e:
            detail = self._read_error_body(e)
            raise RelayError(e.code, detail) from e

    @staticmethod
    def _read_error_body(error: urllib.error.HTTPError) -> str:
        """Read and decode the error response body.

        Attempts to parse as JSON for a ``detail`` or ``error`` field.
        Falls back to the raw body string.

        Args:
            error: The HTTPError to read from.

        Returns:
            A human-readable error string.
        """
        try:
            raw = error.read().decode("utf-8")
        except Exception:
            return f"HTTP {error.code}"

        try:
            data = json.loads(raw)
            # Common API error patterns.
            return str(data.get("detail") or data.get("error") or raw)
        except (json.JSONDecodeError, AttributeError):
            return raw
