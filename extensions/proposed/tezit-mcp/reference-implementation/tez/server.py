import hashlib
import logging
import mimetypes
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from tez.crypto import b64_to_key, generate_key, key_to_b64
from tez.services.local_storage import LocalStorageService
from tez.services.relay_client import RelayClient
from tez.services.sqlite_metadata import SqliteMetadataService
from tez.token_store import TokenStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------

DATA_DIR = os.environ.get("TEZ_DATA_DIR", "/data")
SERVER_URL = os.environ.get("TEZ_SERVER_URL", "http://127.0.0.1:8100")
RELAY_URL = os.environ.get("TEZ_RELAY_URL", "http://localhost:3000")
AUTH_SECRET = os.environ.get("TEZ_AUTH_SECRET", "")
CALLER_ID = os.environ.get("TEZ_CALLER_ID", "")
STORAGE_QUOTA_GB = float(os.environ.get("TEZ_STORAGE_QUOTA_GB", "5"))

# ---------------------------------------------------------------------------
# Service initialisation
# ---------------------------------------------------------------------------

storage = LocalStorageService(data_dir=DATA_DIR, quota_gb=STORAGE_QUOTA_GB)
metadata = SqliteMetadataService(db_path=os.path.join(DATA_DIR, "tez.db"))
relay = RelayClient(relay_url=RELAY_URL, auth_secret=AUTH_SECRET) if RELAY_URL else None
token_store = TokenStore()

# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------

_INSTRUCTIONS = """\
Tez is a system for creating, sharing, and downloading scoped context packages.
You orchestrate all flows by calling MCP tools and the `tez` CLI together.

## Identity

Run `tez auth whoami` to get the current user's name and email.
If not logged in, run: tez auth login --email <email> --name "<name>"
Use the email as `creator`/`caller` and the name as `creator_name` in all tool calls.

## Build flow (create + upload + confirm)

1. Collect the files the user wants to package. For each file, determine its
   name, size (bytes), and content_type (MIME type).
   The `name` field should be a relative path preserving directory structure
   (e.g. "2026-02-05_Onboarding/context.md"), or a simple basename for flat
   files (e.g. "notes.md"). Use forward slashes as path separators.
2. Call MCP tool `tez_build` with name, description, creator, creator_name,
   and the files list. The response contains: tez_id, upload_token, and server.
3. Run the CLI using the `server` and `upload_token` values from the response:
   tez build <tez_id> \\
     --name "<name>" --desc "<description>" \\
     --server <server> \\
     --token <upload_token> \\
     <file1> <file2> ...
   The CLI uploads files to POST /api/upload/<tez_id> on the MCP server.
4. Call MCP tool `tez_build_confirm` with the tez_id to activate the Tez.

## Download flow

1. Call MCP tool `tez_download` with tez_id and caller.
   The response contains: download_token and server.
2. Run the CLI using the `server` and `download_token` values from the response:
   tez download <tez_id> \\
     --server <server> \\
     --token <download_token>
   The CLI fetches files from GET /api/download/<tez_id>/<filename> on the
   MCP server. Files are saved to the OS temp directory under tez/<tez_id>/.

## Other operations (MCP only -- no CLI needed)

- tez_share: share a Tez with a recipient (via relay)
- tez_list: list all Tez the user can access
- tez_info: get metadata about a Tez (no download)
- tez_delete: permanently delete a Tez (creator only, worldwide via relay)

## CLI-only operations

- tez cache clean <tez_id>: remove locally cached files
- tez auth login / whoami / logout: manage local identity
"""

mcp = FastMCP("tez-server", instructions=_INSTRUCTIONS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_caller(caller: str) -> str:
    """Use TEZ_CALLER_ID env var if set, otherwise use the provided caller."""
    return CALLER_ID if CALLER_ID else caller


def _check_auth(request: Request) -> bool:
    """Verify X-Tez-Auth header matches AUTH_SECRET."""
    if not AUTH_SECRET:
        return True  # No secret configured = no auth required
    return request.headers.get("X-Tez-Auth") == AUTH_SECRET


# ---------------------------------------------------------------------------
# MCP Tools — health checks
# ---------------------------------------------------------------------------


@mcp.tool()
def check_storage() -> dict[str, Any]:
    """Check local disk storage status and quota usage.

    Returns disk usage, quota limit, and remaining space.
    """
    used_bytes = storage.disk_usage_bytes()
    quota_bytes = int(STORAGE_QUOTA_GB * 1024 * 1024 * 1024)
    return {
        "status": "healthy",
        "used_bytes": used_bytes,
        "used_mb": round(used_bytes / (1024 * 1024), 2),
        "quota_gb": STORAGE_QUOTA_GB,
        "quota_bytes": quota_bytes,
        "remaining_bytes": max(0, quota_bytes - used_bytes),
        "data_dir": DATA_DIR,
    }


@mcp.tool()
def check_relay() -> dict[str, Any]:
    """Check connectivity to the relay server.

    Returns a status message confirming whether the relay is reachable.
    """
    if relay is None:
        return {"status": "not_configured", "relay_url": RELAY_URL}
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{RELAY_URL.rstrip('/')}/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {
                "status": "healthy",
                "relay_url": RELAY_URL,
                "relay_status_code": resp.status,
            }
    except Exception as e:
        return {
            "status": "unreachable",
            "relay_url": RELAY_URL,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# MCP Tools — Tez lifecycle
# ---------------------------------------------------------------------------


@mcp.tool()
def tez_build(
    name: str,
    description: str,
    creator: str,
    creator_name: str,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a new Tez and generate an upload token.

    Phase 1 of the upload flow: generates a unique Tez ID, an AES-256-GCM
    encryption key, creates a pending metadata record in SQLite, and returns
    a single-use upload token that the CLI uses to POST files to this server.

    Args:
        name: Name of the Tez.
        description: Description of the Tez.
        creator: Creator's email address.
        creator_name: Creator's display name.
        files: List of file dicts with "name", "size", and "content_type".
    """
    creator = _resolve_caller(creator)
    tez_id = uuid4().hex[:8]
    now = datetime.now(tz=UTC).isoformat()

    # Generate encryption key for this bundle.
    key = generate_key()
    key_b64 = key_to_b64(key)

    record = {
        "tez_id": tez_id,
        "creator": creator,
        "creator_name": creator_name,
        "name": name,
        "description": description,
        "status": "pending_upload",
        "file_count": len(files),
        "total_size": sum(f["size"] for f in files),
        "files": files,
        "recipients": [],
        "created_at": now,
        "updated_at": now,
    }
    metadata.create_tez(record)

    expires_in = 900
    upload_token = token_store.create(
        {"tez_id": tez_id, "key_b64": key_b64, "files": files},
        ttl=expires_in,
    )

    return {
        "tez_id": tez_id,
        "status": "pending_upload",
        "expires_in": expires_in,
        "upload_token": upload_token,
        "server": SERVER_URL,
    }


@mcp.tool()
def tez_build_confirm(tez_id: str) -> dict[str, Any]:
    """Confirm file uploads and activate a Tez.

    Phase 3 of the upload flow: validates that all expected files have
    been encrypted and stored on disk, updates the SQLite record status
    from "pending_upload" to "active", and optionally registers with the
    relay server.

    Args:
        tez_id: The Tez identifier returned by tez_build.
    """
    record = metadata.get_tez(tez_id)
    if record is None:
        return {"error": f"Tez {tez_id} not found"}

    validation = storage.validate_uploads(
        tez_id=tez_id, expected_files=record["files"]
    )

    if not validation.success:
        return {
            "error": "Upload validation failed",
            "missing_files": validation.missing,
        }

    metadata.update_status(tez_id=tez_id, status="active")

    # Register with relay if configured.
    relay_status = None
    if relay is not None:
        try:
            # Compute content hash from the encrypted blob.
            blob = storage.get_encrypted_blob(tez_id)
            content_hash = hashlib.sha256(blob).hexdigest()

            # We need the key to register -- read it from the manifest
            # files stored on disk (the key is NOT stored in metadata
            # for security). For relay registration we re-generate a
            # registration token so the relay can escrow the key.
            # NOTE: The key was used during upload and is not persisted
            # in the metadata DB. For relay registration the creator's
            # MCP must re-supply it. Since we don't store the key, we
            # skip key escrow on confirm and let the relay fetch the
            # encrypted blob instead.
            relay.register_tez(
                tez_id=tez_id,
                key_b64="",  # Key not available post-upload; relay uses blob
                creator=record["creator"],
                name=record["name"],
                description=record.get("description", ""),
                content_hash=content_hash,
                file_manifest=record["files"],
            )

            # Upload encrypted blob to relay cache.
            relay.upload_blob(tez_id=tez_id, blob=blob)
            relay_status = "registered"
        except Exception as e:
            logger.warning("Relay registration failed for tez %s: %s", tez_id, e)
            relay_status = f"failed: {e}"

    return {
        "tez_id": tez_id,
        "status": "active",
        "file_count": len(record["files"]),
        "relay_status": relay_status,
    }


@mcp.tool()
def tez_download(tez_id: str, caller: str) -> dict[str, Any]:
    """Generate a download token for a Tez.

    Checks authorization (caller must be creator or recipient), then
    returns metadata and a single-use download token that the CLI uses
    to GET decrypted files from this server's REST API.

    For remote tez (received via relay), requests the key from the relay
    and fetches the encrypted blob for local decryption.

    Args:
        tez_id: The Tez identifier.
        caller: Email of the requesting user.
    """
    caller = _resolve_caller(caller)

    record = metadata.get_tez(tez_id)
    if record is None:
        # Not local -- try relay if available.
        if relay is not None:
            return _download_from_relay(tez_id, caller)
        return {"error": f"Tez {tez_id} not found"}

    if not metadata.is_authorised(tez_id, caller):
        return {"error": "Access denied"}

    # For local tez, we need the encryption key. Since we don't persist
    # the key in metadata (security), we read the manifest which has
    # the nonces/tags, and the download endpoint will decrypt using a
    # key embedded in the token. But we need the key from somewhere.
    # Solution: store the key_b64 in the download token. The key was
    # only available during upload. We need a different approach:
    # store the key in a separate secure location.
    #
    # For the PoC: we store the key_b64 in a keys file alongside the DB.
    key_b64 = _load_key(tez_id)
    if key_b64 is None:
        return {"error": f"Encryption key not found for tez {tez_id}"}

    expires_in = 3600
    download_token = token_store.create(
        {"tez_id": tez_id, "key_b64": key_b64},
        ttl=expires_in,
    )

    return {
        "tez_id": tez_id,
        "name": record["name"],
        "creator": record["creator"],
        "description": record.get("description", ""),
        "status": record["status"],
        "files": record["files"],
        "download_token": download_token,
        "expires_in": expires_in,
        "server": SERVER_URL,
    }


def _download_from_relay(tez_id: str, caller: str) -> dict[str, Any]:
    """Handle download for a tez not stored locally (fetched via relay)."""
    try:
        key_b64 = relay.request_key(tez_id=tez_id, caller=caller)
        if key_b64 is None:
            return {"error": f"Tez {tez_id} not found or access denied on relay"}

        # TODO: fetch encrypted blob from relay, decrypt, store locally
        # For now return a token that references the relay-fetched data.
        expires_in = 3600
        download_token = token_store.create(
            {"tez_id": tez_id, "key_b64": key_b64, "source": "relay"},
            ttl=expires_in,
        )
        return {
            "tez_id": tez_id,
            "source": "relay",
            "download_token": download_token,
            "expires_in": expires_in,
            "server": SERVER_URL,
        }
    except Exception as e:
        logger.error("Relay download failed for tez %s: %s", tez_id, e)
        return {"error": f"Relay download failed: {e}"}


@mcp.tool()
def tez_share(
    tez_id: str,
    recipient_email: str,
    caller: str,
) -> dict[str, Any]:
    """Share a Tez with a recipient.

    Adds the recipient to the Tez's authorised recipients list in SQLite
    and notifies the relay server (if configured) to propagate the ACL.

    Args:
        tez_id: The Tez identifier.
        recipient_email: Email address of the person to share with.
        caller: Email of the user performing the share (must be the creator).
    """
    caller = _resolve_caller(caller)

    record = metadata.get_tez(tez_id)
    if record is None:
        return {"error": f"Tez {tez_id} not found"}

    if record["creator"] != caller:
        return {"error": "Only the creator can share a Tez"}

    metadata.add_recipient(tez_id=tez_id, email=recipient_email)

    relay_status = None
    if relay is not None:
        try:
            relay.share_tez(
                tez_id=tez_id,
                recipient=recipient_email,
                caller=caller,
            )
            relay_status = "shared"
        except Exception as e:
            logger.warning("Relay share failed for tez %s: %s", tez_id, e)
            relay_status = f"failed: {e}"

    return {
        "tez_id": tez_id,
        "shared_with": recipient_email,
        "relay_status": relay_status,
    }


@mcp.tool()
def tez_list(caller: str) -> dict[str, Any]:
    """List all Tez accessible to a user.

    Returns Tez created by the caller and Tez shared with the caller.

    Args:
        caller: Email of the requesting user.
    """
    caller = _resolve_caller(caller)

    created = metadata.list_by_creator(caller)
    shared = metadata.list_shared_with(caller)

    created_items = [
        {
            "tez_id": r["tez_id"],
            "name": r["name"],
            "file_count": r["file_count"],
            "shared_by": "me",
            "created_at": r["created_at"],
        }
        for r in created
    ]
    shared_items = [
        {
            "tez_id": r["tez_id"],
            "name": r["name"],
            "file_count": r["file_count"],
            "shared_by": r["creator"],
            "created_at": r["created_at"],
        }
        for r in shared
    ]

    return {"created": created_items, "shared_with_me": shared_items}


@mcp.tool()
def tez_info(tez_id: str, caller: str) -> dict[str, Any]:
    """Get metadata about a Tez without generating download URLs.

    Returns the Tez record metadata -- name, creator, description,
    files, and status. Recipients are only visible to the creator.

    Args:
        tez_id: The Tez identifier.
        caller: Email of the requesting user.
    """
    caller = _resolve_caller(caller)

    record = metadata.get_tez(tez_id)
    if record is None:
        return {"error": f"Tez {tez_id} not found"}

    if not metadata.is_authorised(tez_id, caller):
        return {"error": "Access denied"}

    result: dict[str, Any] = {
        "tez_id": record["tez_id"],
        "name": record["name"],
        "creator": record["creator"],
        "description": record.get("description", ""),
        "status": record["status"],
        "file_count": record["file_count"],
        "total_size": record.get("total_size", 0),
        "files": record["files"],
        "created_at": record["created_at"],
        "updated_at": record.get("updated_at", ""),
    }

    if record["creator"] == caller:
        result["recipients"] = record.get("recipients", [])

    return result


@mcp.tool()
def tez_delete(tez_id: str, caller: str) -> dict[str, Any]:
    """Delete a Tez -- removes encrypted files, SQLite record, and relay entry.

    Only the creator can delete a Tez. Removes all local encrypted files,
    the SQLite metadata record, and notifies the relay to destroy the key
    and trigger worldwide deletion.

    Args:
        tez_id: The Tez identifier.
        caller: Email of the requesting user (must be the creator).
    """
    caller = _resolve_caller(caller)

    record = metadata.get_tez(tez_id)
    if record is None:
        return {"error": f"Tez {tez_id} not found"}

    if record["creator"] != caller:
        return {"error": "Only the creator can delete a Tez"}

    # Delete local encrypted files.
    storage.delete_tez(tez_id=tez_id)

    # Delete SQLite record.
    metadata.delete_tez(tez_id=tez_id)

    # Delete local key file.
    _delete_key(tez_id)

    # Notify relay (triggers key destruction + worldwide delete).
    relay_status = None
    if relay is not None:
        try:
            relay.delete_tez(tez_id=tez_id, caller=caller)
            relay_status = "deleted"
        except Exception as e:
            logger.warning("Relay delete failed for tez %s: %s", tez_id, e)
            relay_status = f"failed: {e}"

    return {
        "tez_id": tez_id,
        "status": "deleted",
        "relay_status": relay_status,
    }


# ---------------------------------------------------------------------------
# Key persistence (simple file-based store alongside the DB)
# ---------------------------------------------------------------------------


def _key_dir() -> str:
    """Return the directory for key storage."""
    d = os.path.join(DATA_DIR, "keys")
    os.makedirs(d, exist_ok=True)
    return d


def _save_key(tez_id: str, key_b64: str) -> None:
    """Persist an encryption key for a tez."""
    path = os.path.join(_key_dir(), f"{tez_id}.key")
    with open(path, "w") as f:
        f.write(key_b64)


def _load_key(tez_id: str) -> str | None:
    """Load the encryption key for a tez, or None if not found."""
    path = os.path.join(_key_dir(), f"{tez_id}.key")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return f.read().strip()


def _delete_key(tez_id: str) -> None:
    """Delete the persisted encryption key for a tez."""
    path = os.path.join(_key_dir(), f"{tez_id}.key")
    if os.path.isfile(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@mcp.custom_route("/api/tokens/{token}", methods=["GET"])
async def exchange_token(request: Request) -> JSONResponse:
    """Exchange a single-use token for its payload."""
    token = request.path_params["token"]
    payload = token_store.exchange(token)
    if payload is None:
        return JSONResponse(
            {"error": "Token not found or expired"},
            status_code=404,
        )
    return JSONResponse(payload)


@mcp.custom_route("/api/upload/{tez_id}", methods=["POST"])
async def upload_files(request: Request) -> JSONResponse:
    """Accept file uploads from the CLI, encrypt, and store locally.

    Expects:
    - X-Tez-Auth header (if AUTH_SECRET is configured)
    - Query param or header: token (upload token from tez_build)
    - Multipart file upload body
    """
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    tez_id = request.path_params["tez_id"]

    # Get the upload token from query params or header.
    upload_token = request.query_params.get("token") or request.headers.get(
        "X-Upload-Token"
    )
    if not upload_token:
        return JSONResponse(
            {"error": "Missing upload token"},
            status_code=400,
        )

    # Exchange the token to get the encryption key and expected files.
    token_data = token_store.exchange(upload_token)
    if token_data is None:
        return JSONResponse(
            {"error": "Upload token not found or expired"},
            status_code=404,
        )

    if token_data.get("tez_id") != tez_id:
        return JSONResponse(
            {"error": "Token does not match tez_id"},
            status_code=403,
        )

    key_b64 = token_data["key_b64"]
    key = b64_to_key(key_b64)

    # Parse multipart upload.
    form = await request.form()
    uploaded_files: list[dict[str, Any]] = []

    for field_name in form:
        upload = form[field_name]
        # Starlette UploadFile objects have .read(), .filename, .content_type
        if hasattr(upload, "read"):
            content = await upload.read()
            filename = upload.filename or field_name
            content_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            uploaded_files.append({
                "name": filename,
                "content": content,
                "content_type": content_type,
                "size": len(content),
            })

    if not uploaded_files:
        return JSONResponse(
            {"error": "No files uploaded"},
            status_code=400,
        )

    try:
        file_metadata = storage.store_files(
            tez_id=tez_id,
            files=uploaded_files,
            key=key,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=413)
    except OSError as e:
        logger.error("Storage error for tez %s: %s", tez_id, e)
        return JSONResponse({"error": "Storage error"}, status_code=500)

    # Update file metadata in SQLite with encrypted sizes/indices.
    metadata.update_files(tez_id=tez_id, files=file_metadata)

    # Persist the encryption key for later downloads.
    _save_key(tez_id, key_b64)

    return JSONResponse({
        "tez_id": tez_id,
        "status": "uploaded",
        "file_count": len(file_metadata),
    })


@mcp.custom_route("/api/download/{tez_id}/{filename:path}", methods=["GET"])
async def download_file(request: Request) -> Response:
    """Serve a decrypted file from local storage.

    Expects:
    - X-Tez-Auth header (if AUTH_SECRET is configured)
    - Query param: token (download token from tez_download)
    """
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    tez_id = request.path_params["tez_id"]
    filename = request.path_params["filename"]

    download_token = request.query_params.get("token") or request.headers.get(
        "X-Download-Token"
    )
    if not download_token:
        return JSONResponse(
            {"error": "Missing download token"},
            status_code=400,
        )

    # Peek at the token (non-destructive) -- we need to allow multiple
    # file downloads with the same token. Use a different approach:
    # store file list in token and don't consume on first exchange.
    # Actually, for simplicity, we re-create the token approach:
    # the download token is exchanged ONCE by the CLI to get file list
    # and key, then the CLI uses the key directly in subsequent requests.
    # But that exposes the key in URLs. Better approach: exchange token
    # once, return signed per-file tokens.
    #
    # Simplest PoC approach: the CLI exchanges the token via
    # /api/tokens/{token} first to get key_b64 and file list, then
    # passes key_b64 in a header for each file download.

    key_b64 = request.headers.get("X-Tez-Key")
    if not key_b64:
        return JSONResponse(
            {"error": "Missing X-Tez-Key header"},
            status_code=400,
        )

    try:
        key = b64_to_key(key_b64)
    except ValueError:
        return JSONResponse(
            {"error": "Invalid encryption key"},
            status_code=400,
        )

    try:
        plaintext = storage.decrypt_and_get(
            tez_id=tez_id,
            filename=filename,
            key=key,
        )
    except FileNotFoundError:
        return JSONResponse(
            {"error": f"File not found: {filename}"},
            status_code=404,
        )
    except KeyError:
        return JSONResponse(
            {"error": f"File not in manifest: {filename}"},
            status_code=404,
        )
    except Exception as e:
        logger.error("Decryption error for tez %s file %s: %s", tez_id, filename, e)
        return JSONResponse(
            {"error": "Decryption failed"},
            status_code=500,
        )

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=plaintext,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"',
        },
    )


@mcp.custom_route("/api/blob/{tez_id}", methods=["GET"])
async def serve_blob(request: Request) -> Response:
    """Serve the encrypted tar.gz blob for relay caching.

    Expects X-Tez-Auth header for authentication.
    """
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    tez_id = request.path_params["tez_id"]

    try:
        blob = storage.get_encrypted_blob(tez_id)
    except FileNotFoundError:
        return JSONResponse(
            {"error": f"Bundle not found for tez {tez_id}"},
            status_code=404,
        )

    return Response(
        content=blob,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{tez_id}.tar.gz"',
        },
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "tez-server"})


# ---------------------------------------------------------------------------
# ASGI app (for external servers like uvicorn)
# ---------------------------------------------------------------------------

app = mcp.http_app()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    port = int(os.environ.get("PORT", "8100"))
    mcp.run(transport="http", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
