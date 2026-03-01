"""SQLite metadata store for tezit records.

Replaces the DynamoDB-backed ``MetadataService`` with a local SQLite
database. Uses WAL mode for improved concurrent read performance and
stores JSON arrays (files, recipients) as TEXT columns with
``json.loads``/``json.dumps`` serialisation.

The schema mirrors the DynamoDB record shape documented in README.md,
with the addition of standard SQL indices for common query patterns.

Thread safety: SQLite with ``check_same_thread=False`` allows sharing
a connection across threads. WAL mode supports concurrent readers.
For the single-process FastMCP server this is sufficient.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS tez (
    tez_id TEXT PRIMARY KEY,
    creator TEXT NOT NULL,
    creator_name TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'pending_upload',
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    files TEXT DEFAULT '[]',
    recipients TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_creator ON tez(creator);
CREATE INDEX IF NOT EXISTS idx_status ON tez(status);
"""


class SqliteMetadataService:
    """SQLite metadata store for tezit records.

    Opens (or creates) a SQLite database at the given path with WAL
    journal mode enabled for better concurrent read performance.

    Args:
        db_path: Filesystem path to the SQLite database file.
            Parent directories are created automatically.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

        logger.info("SQLite metadata store opened at %s", self._db_path)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_tez(self, record: dict[str, Any]) -> None:
        """Insert a new tezit record.

        Required fields in ``record``:
            tez_id, creator, creator_name, name, status,
            file_count, total_size, files, recipients,
            created_at, updated_at

        Optional: description (defaults to empty string).

        Args:
            record: Complete tezit metadata dict.

        Raises:
            sqlite3.IntegrityError: If tez_id already exists.
        """
        files_json = json.dumps(record.get("files", []))
        recipients_json = json.dumps(record.get("recipients", []))

        try:
            self._conn.execute(
                """\
                INSERT INTO tez (
                    tez_id, creator, creator_name, name, description,
                    status, file_count, total_size, files, recipients,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["tez_id"],
                    record["creator"],
                    record["creator_name"],
                    record["name"],
                    record.get("description", ""),
                    record.get("status", "pending_upload"),
                    record.get("file_count", 0),
                    record.get("total_size", 0),
                    files_json,
                    recipients_json,
                    record["created_at"],
                    record["updated_at"],
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            logger.warning("Tez %s already exists", record["tez_id"])
            raise

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_tez(self, tez_id: str) -> dict[str, Any] | None:
        """Fetch a tezit record by ID.

        Args:
            tez_id: The tezit identifier.

        Returns:
            The full record as a dict with ``files`` and
            ``recipients`` deserialised from JSON, or ``None``
            if not found.
        """
        cursor = self._conn.execute(
            "SELECT * FROM tez WHERE tez_id = ?",
            (tez_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_status(self, tez_id: str, status: str) -> None:
        """Update the status field of a tezit.

        Also updates the ``updated_at`` timestamp.

        Args:
            tez_id: The tezit identifier.
            status: New status value (e.g. ``"active"``,
                ``"pending_upload"``).

        Raises:
            ValueError: If the tez_id does not exist.
        """
        now = datetime.now(tz=UTC).isoformat()
        cursor = self._conn.execute(
            """\
            UPDATE tez
            SET status = ?, updated_at = ?
            WHERE tez_id = ?
            """,
            (status, now, tez_id),
        )
        self._conn.commit()

        if cursor.rowcount == 0:
            msg = f"Tez {tez_id} not found"
            raise ValueError(msg)

    def add_recipient(self, tez_id: str, email: str) -> None:
        """Add a recipient email to a tezit's recipients list.

        No-op if the email is already in the recipients list.
        Updates the ``updated_at`` timestamp.

        Args:
            tez_id: The tezit identifier.
            email: Recipient email address to add.

        Raises:
            ValueError: If the tez_id does not exist.
        """
        record = self.get_tez(tez_id)
        if record is None:
            msg = f"Tez {tez_id} not found"
            raise ValueError(msg)

        recipients: list[str] = record.get("recipients", [])
        if email in recipients:
            return

        recipients.append(email)
        now = datetime.now(tz=UTC).isoformat()

        self._conn.execute(
            """\
            UPDATE tez
            SET recipients = ?, updated_at = ?
            WHERE tez_id = ?
            """,
            (json.dumps(recipients), now, tez_id),
        )
        self._conn.commit()

    def update_files(self, tez_id: str, files: list[dict[str, Any]]) -> None:
        """Update the files metadata for a tezit.

        Used after ``store_files`` to persist the file manifest
        metadata (encrypted sizes, indices) back to the record.

        Args:
            tez_id: The tezit identifier.
            files: Updated file metadata list.

        Raises:
            ValueError: If the tez_id does not exist.
        """
        now = datetime.now(tz=UTC).isoformat()
        cursor = self._conn.execute(
            """\
            UPDATE tez
            SET files = ?, file_count = ?, updated_at = ?
            WHERE tez_id = ?
            """,
            (json.dumps(files), len(files), now, tez_id),
        )
        self._conn.commit()

        if cursor.rowcount == 0:
            msg = f"Tez {tez_id} not found"
            raise ValueError(msg)

    # ------------------------------------------------------------------
    # Query / List
    # ------------------------------------------------------------------

    def list_by_creator(self, email: str) -> list[dict[str, Any]]:
        """List all tezits created by a specific user.

        Results are ordered by ``created_at`` descending (newest first).

        Args:
            email: Creator's email address.

        Returns:
            List of tezit records (may be empty).
        """
        cursor = self._conn.execute(
            """\
            SELECT * FROM tez
            WHERE creator = ?
            ORDER BY created_at DESC
            """,
            (email,),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def list_shared_with(self, email: str) -> list[dict[str, Any]]:
        """List all tezits shared with a specific user.

        Searches the JSON ``recipients`` column for the email address.
        Uses SQLite's ``json_each`` for correct JSON array searching.

        Note: Full table scan with JSON parsing. Acceptable for the
        current fleet scale (< 10k records per PA).

        Args:
            email: Recipient's email address.

        Returns:
            List of tezit records (may be empty).
        """
        # Use json_each to properly search within the JSON array,
        # rather than substring matching which could produce false
        # positives (e.g. "a@b.com" matching "ba@b.com.au").
        cursor = self._conn.execute(
            """\
            SELECT t.* FROM tez t
            WHERE EXISTS (
                SELECT 1 FROM json_each(t.recipients) AS r
                WHERE r.value = ?
            )
            ORDER BY t.created_at DESC
            """,
            (email,),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Authorisation
    # ------------------------------------------------------------------

    def is_authorised(self, tez_id: str, email: str) -> bool:
        """Check if a user is authorised to access a tezit.

        A user is authorised if they are either:
        - The creator of the tezit.
        - Listed in the tezit's recipients array.

        Returns ``False`` for nonexistent tez IDs (does not reveal
        existence to unauthorised callers).

        Args:
            tez_id: The tezit identifier.
            email: User's email address.

        Returns:
            True if authorised, False otherwise.
        """
        record = self.get_tez(tez_id)
        if record is None:
            return False
        if record.get("creator") == email:
            return True
        return email in record.get("recipients", [])

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_tez(self, tez_id: str) -> None:
        """Delete a tezit record from the database.

        Safe to call on nonexistent tez IDs (no-op).

        Args:
            tez_id: The tezit identifier.
        """
        self._conn.execute(
            "DELETE FROM tez WHERE tez_id = ?",
            (tez_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection.

        Safe to call multiple times. After closing, no further
        operations should be attempted.
        """
        self._conn.close()
        logger.info("SQLite metadata store closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict with JSON deserialisation.

        The ``files`` and ``recipients`` columns are stored as JSON
        strings and are deserialised back to Python lists.

        Args:
            row: A sqlite3.Row from a query result.

        Returns:
            A dict with all columns, with JSON fields parsed.
        """
        d: dict[str, Any] = dict(row)

        # Deserialise JSON columns.
        for json_col in ("files", "recipients"):
            if json_col in d and isinstance(d[json_col], str):
                try:
                    d[json_col] = json.loads(d[json_col])
                except (json.JSONDecodeError, TypeError):
                    d[json_col] = []

        return d
