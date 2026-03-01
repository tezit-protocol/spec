# tezit-mcp Reference Implementation

Python MCP server implementing the `tezit-mcp` extension for the Tezit Protocol.

## Overview

This reference implementation exposes 9 MCP tools that map to Tezit Protocol operations, enabling AI agents to create, encrypt, share, and manage tezits through standard MCP tool calls.

## Requirements

- Python 3.12+
- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server framework
- `cryptography` — AES-256-GCM encryption
- SQLite 3.35+ (JSON array support)

## Setup

```bash
pip install -e .
```

Configure the relay URL (optional, for cross-node sharing):

```bash
export TEZ_RELAY_URL=https://your-relay-server.example.com
```

## Running

```bash
# As MCP server (stdio transport)
python -m tez

# With custom data directory
TEZ_DATA_DIR=/path/to/data python -m tez
```

## Architecture

```
tez/
├── server.py              # MCP tool definitions + REST endpoints
├── crypto.py              # AES-256-GCM encryption with PBKDF2 key derivation
├── bundle.py              # Tez bundle creation and packaging
├── cli.py                 # Command-line interface
├── token_store.py         # Download token management
├── __main__.py            # Entry point
└── services/
    ├── sqlite_metadata.py # SQLite metadata store with JSON array support
    ├── local_storage.py   # Local filesystem storage (directory-per-tez)
    └── relay_client.py    # Relay federation client for cross-node sharing
```

### Key Design Decisions

- **Local-first**: All data stored locally by default. Relay is optional.
- **Encryption at rest**: Every tez is encrypted with AES-256-GCM. Keys derived via PBKDF2-SHA256 with 100,000 iterations.
- **SQLite metadata**: Lightweight, embedded, no external database dependency.
- **Relay federation**: Stateless relay broker enables cross-node sharing without direct connectivity.

## MCP Tools

| Tool | Description |
|------|-------------|
| `check_storage` | Verify local storage health |
| `check_relay` | Verify relay connectivity |
| `tez_build` | Create a new tez with context |
| `tez_build_confirm` | Finalize a staged tez |
| `tez_download` | Download and decrypt a tez |
| `tez_share` | Share a tez via relay |
| `tez_list` | List created and shared tezits |
| `tez_info` | Get tez metadata |
| `tez_delete` | Delete a tez |

## License

See the repository root for license information.