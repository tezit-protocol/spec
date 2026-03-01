# tezit-mcp: Model Context Protocol Integration

**Extension ID:** `tezit-mcp`
**Extension Version:** 1.0
**Status:** Proposed
**Proposed by:** Community Contributor
**Minimum Protocol Version:** Tezit Protocol v1.2
**Related Extensions:** `tezit-encryption` (leveraged for AES-256-GCM)

---

## Purpose

AI agents operating through the Model Context Protocol (MCP) currently have no standardized way to interact with the Tezit Protocol. Each implementation must create custom integrations, leading to inconsistent tool interfaces, incompatible parameter conventions, and fragmented ecosystem tooling.

This extension defines a standard mapping between MCP tool calls and Tezit Protocol operations, enabling any MCP-compatible AI agent to create, encrypt, share, and manage tezits through a consistent tool interface.

**Who benefits:**

- **AI agent platforms** that want to offer Tezit capabilities without designing custom tool schemas
- **MCP server implementers** who need a reference for how Tezit operations map to tool calls
- **Multi-agent deployments** where agents on different nodes need to share tezits through a common interface
- **Tool aggregators** that catalog MCP tools and need a stable, well-specified Tezit integration

**What this extension provides:**

1. **Tool definitions** — 9 MCP tools covering the full tezit lifecycle (create, build, share, read, list, search, delete, and system health)
2. **Encryption integration** — Seamless AES-256-GCM encryption leveraging the `tezit-encryption` standard extension
3. **Local-first architecture** — SQLite metadata and filesystem storage with relay federation for cross-node sharing
4. **Parameter conventions** — Standardized parameter names, types, and return schemas across all tools

---

## Schema

### Extension Manifest

The extension manifest file is placed at `extensions/tezit-mcp/manifest.json` within any Tez created by an MCP server implementing this extension:

```json
{
  "extension_id": "tezit-mcp",
  "extension_version": "1.0",
  "name": "Model Context Protocol Integration",
  "description": "Standard MCP tool interface for Tezit Protocol operations",
  "author": "Community Contributor",
  "url": "https://github.com/tezit-protocol/spec/extensions/proposed/tezit-mcp"
}
```

### MCP Tool Definitions

This extension defines 9 MCP tools. Implementations MUST expose all 9 tools. Tool names use the `tez_` prefix to avoid namespace collisions with other MCP tools.

#### System Tools

##### `check_storage`

Verify local storage health and capacity.

**Parameters:** None

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "status": { "type": "string", "enum": ["healthy", "degraded", "unavailable"] },
    "storage_path": { "type": "string" },
    "tez_count": { "type": "integer" },
    "disk_usage_bytes": { "type": "integer" }
  }
}
```

##### `check_relay`

Verify relay server connectivity for cross-node sharing.

**Parameters:** None

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "status": { "type": "string", "enum": ["connected", "disconnected", "unavailable"] },
    "relay_url": { "type": "string" },
    "latency_ms": { "type": "number" }
  }
}
```

#### Lifecycle Tools

##### `tez_build`

Create a new tez with initial context. This begins the tez creation process — the tez is staged locally but not finalized until `tez_build_confirm` is called.

**Parameters:**
```json
{
  "type": "object",
  "required": ["title", "context", "creator"],
  "properties": {
    "title": {
      "type": "string",
      "description": "Human-readable title for the tez"
    },
    "context": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "content"],
        "properties": {
          "type": { "type": "string", "enum": ["text", "code", "data", "reference"] },
          "content": { "type": "string" },
          "filename": { "type": "string" },
          "language": { "type": "string" },
          "description": { "type": "string" }
        }
      },
      "description": "Array of context items to include in the tez"
    },
    "creator": {
      "type": "string",
      "format": "email",
      "description": "Email address of the creating user"
    },
    "synthesis_prompt": {
      "type": "string",
      "description": "Optional prompt for generating a synthesis of the bundled context"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Optional tags for categorization and search"
    }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" },
    "status": { "type": "string", "enum": ["staged", "error"] },
    "file_count": { "type": "integer" },
    "total_size_bytes": { "type": "integer" },
    "encryption": {
      "type": "object",
      "properties": {
        "algorithm": { "type": "string", "const": "AES-256-GCM" },
        "key_derivation": { "type": "string", "const": "PBKDF2-SHA256" }
      }
    }
  }
}
```

##### `tez_build_confirm`

Finalize a staged tez, making it available for sharing and download.

**Parameters:**
```json
{
  "type": "object",
  "required": ["tez_id"],
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "tez_id": { "type": "string" },
    "status": { "type": "string", "enum": ["confirmed", "error"] },
    "download_token": { "type": "string" },
    "relay_registered": { "type": "boolean" }
  }
}
```

#### Access Tools

##### `tez_download`

Download and decrypt a tez by ID.

**Parameters:**
```json
{
  "type": "object",
  "required": ["tez_id", "caller"],
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" },
    "caller": { "type": "string", "format": "email" }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "tez_id": { "type": "string" },
    "title": { "type": "string" },
    "creator": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "context": { "type": "array" },
    "synthesis": { "type": "string" }
  }
}
```

##### `tez_list`

List tezits created by or shared with the caller.

**Parameters:**
```json
{
  "type": "object",
  "required": ["caller"],
  "properties": {
    "caller": { "type": "string", "format": "email" }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "my_tezits": {
      "type": "array",
      "items": { "$ref": "#/definitions/TezSummary" }
    },
    "shared_with_me": {
      "type": "array",
      "items": { "$ref": "#/definitions/TezSummary" }
    }
  }
}
```

##### `tez_info`

Get metadata about a specific tez without downloading its contents.

**Parameters:**
```json
{
  "type": "object",
  "required": ["tez_id", "caller"],
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" },
    "caller": { "type": "string", "format": "email" }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "tez_id": { "type": "string" },
    "title": { "type": "string" },
    "creator": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "file_count": { "type": "integer" },
    "total_size_bytes": { "type": "integer" },
    "recipients": { "type": "array", "items": { "type": "string" } },
    "tags": { "type": "array", "items": { "type": "string" } }
  }
}
```

#### Sharing Tools

##### `tez_share`

Share a tez with another user via relay federation.

**Parameters:**
```json
{
  "type": "object",
  "required": ["tez_id", "recipient_email", "caller"],
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" },
    "recipient_email": { "type": "string", "format": "email" },
    "caller": { "type": "string", "format": "email" },
    "message": { "type": "string", "description": "Optional message to the recipient" }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "shared_with": { "type": "string" },
    "relay_delivered": { "type": "boolean" },
    "download_token": { "type": "string" }
  }
}
```

#### Management Tools

##### `tez_delete`

Delete a tez and its associated files. Only the creator may delete a tez.

**Parameters:**
```json
{
  "type": "object",
  "required": ["tez_id", "caller"],
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" },
    "caller": { "type": "string", "format": "email" }
  }
}
```

**Returns:**
```json
{
  "type": "object",
  "properties": {
    "deleted": { "type": "boolean" },
    "tez_id": { "type": "string" }
  }
}
```

### Common Definitions

#### TezSummary

```json
{
  "type": "object",
  "properties": {
    "tez_id": { "type": "string", "format": "uuid" },
    "title": { "type": "string" },
    "creator": { "type": "string", "format": "email" },
    "created_at": { "type": "string", "format": "date-time" },
    "file_count": { "type": "integer" },
    "shared_by": { "type": "string", "format": "email", "description": "Present only in shared_with_me results" }
  }
}
```

---

## Architecture

### Local-First Design

Implementations MUST store tez data locally by default. The recommended architecture:

- **Metadata store:** SQLite database with JSON array support for recipients and tags
- **Content store:** Local filesystem with directory-per-tez layout
- **Encryption:** AES-256-GCM with PBKDF2-SHA256 key derivation (leveraging `tezit-encryption`)
- **Federation:** Relay server for cross-node sharing (optional but recommended)

### Encryption

All tez content MUST be encrypted at rest using AES-256-GCM. Key derivation uses PBKDF2 with SHA-256, 100,000 iterations, and a random 16-byte salt per tez. The encryption key is derived from a node-specific secret.

Implementations that support the `tezit-encryption` standard extension SHOULD use its key management conventions. Implementations MAY use their own key management if `tezit-encryption` is not available.

### Relay Federation

Cross-node sharing uses a relay server that brokers connections between MCP server instances. The relay protocol is:

1. **Registration:** On `tez_build_confirm`, the MCP server registers the tez's download token with the relay
2. **Sharing:** On `tez_share`, the relay notifies the recipient's node that a tez is available
3. **Download:** The recipient's MCP server fetches the tez from the creator's node via the relay

The relay URL MUST be configurable via the `TEZ_RELAY_URL` environment variable. Implementations MUST function without a relay (local-only mode) when no relay is configured.

---

## Examples

### Example: Creating and Sharing a Tez

**Step 1: Build a tez**

MCP tool call:
```json
{
  "tool": "tez_build",
  "arguments": {
    "title": "Q4 Research Summary",
    "context": [
      {
        "type": "text",
        "content": "Key findings from the quarterly analysis...",
        "filename": "summary.md",
        "description": "Executive summary"
      },
      {
        "type": "data",
        "content": "{\"revenue\": 1250000, \"growth\": 0.15}",
        "filename": "metrics.json",
        "description": "Revenue metrics"
      }
    ],
    "creator": "analyst@example.com",
    "tags": ["research", "quarterly"]
  }
}
```

Response:
```json
{
  "tez_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "staged",
  "file_count": 2,
  "total_size_bytes": 4096,
  "encryption": {
    "algorithm": "AES-256-GCM",
    "key_derivation": "PBKDF2-SHA256"
  }
}
```

**Step 2: Confirm the build**

```json
{
  "tool": "tez_build_confirm",
  "arguments": {
    "tez_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

**Step 3: Share with a colleague**

```json
{
  "tool": "tez_share",
  "arguments": {
    "tez_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "recipient_email": "colleague@example.com",
    "caller": "analyst@example.com",
    "message": "Here's the Q4 summary we discussed"
  }
}
```

### Example: Receiving and Reading a Shared Tez

```json
{
  "tool": "tez_list",
  "arguments": {
    "caller": "colleague@example.com"
  }
}
```

Response:
```json
{
  "my_tezits": [],
  "shared_with_me": [
    {
      "tez_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Q4 Research Summary",
      "creator": "analyst@example.com",
      "created_at": "2026-02-28T12:00:00Z",
      "file_count": 2,
      "shared_by": "analyst@example.com"
    }
  ]
}
```

---

## Compatibility Notes

### Minimum Protocol Version

This extension requires **Tezit Protocol v1.2** or later. It relies on the manifest extension registry introduced in v1.2.

### Graceful Degradation

Tezits created by an MCP server implementing this extension remain fully functional without MCP. The tez bundle format is standard Tezit Protocol — any compliant reader can open and read the contents. The MCP tools are an interface layer, not a data format dependency.

### Conflicts

This extension does not conflict with any existing standard or proposed extensions. It leverages `tezit-encryption` when available but does not require it (implementations MAY use their own encryption).

### Related Extensions

- **`tezit-encryption`** — This extension's AES-256-GCM implementation follows the `tezit-encryption` key management conventions where applicable.
- **`tezit-signatures`** — MCP servers implementing this extension SHOULD support `tezit-signatures` for bundle integrity verification on shared tezits.

---

## Reference Implementation

A Python reference implementation is provided in the `reference-implementation/` directory. It uses [FastMCP](https://github.com/jlowin/fastmcp) for the MCP server and demonstrates all 9 tools with SQLite metadata, local filesystem storage, AES-256-GCM encryption, and relay federation.

See `reference-implementation/README.md` for setup and usage instructions.

---

## Production Evidence

This extension has been tested in production with 18 AI agents across 5 nodes, handling cross-node tez sharing with end-to-end encryption. The reference implementation is derived from this production deployment.