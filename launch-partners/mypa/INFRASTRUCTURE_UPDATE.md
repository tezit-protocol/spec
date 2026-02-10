# MyPA Infrastructure Update — February 10, 2026

**From:** MyPA.chat (Launch Partner)
**Date:** February 10, 2026
**Status:** Production — all systems live and verified
**Repo:** [github.com/ragurob/MyPA.chat](https://github.com/ragurob/MyPA.chat) (monorepo)

---

## Executive Summary

Since our last update (Feb 8-9), we have shipped a **dedicated Tezit Relay node**, a **live federation system with Ed25519 cryptographic signing**, **real-time messaging via Server-Sent Events**, **orchestrated user registration**, and a **unified adapter architecture** that makes the relay the canonical message store.

This document covers everything the Tezit Protocol team needs to know — the node architecture, federation implementation details, infrastructure map, deployment model, and what the website needs to explain about nodes and federation.

---

## Table of Contents

1. [The Tezit Relay Node](#1-the-tezit-relay-node)
2. [Federation System](#2-federation-system)
3. [Infrastructure Map](#3-infrastructure-map)
4. [Adapter Architecture](#4-adapter-architecture)
5. [Orchestrated Registration](#5-orchestrated-registration)
6. [Real-Time Messaging (SSE)](#6-real-time-messaging-sse)
7. [Federation E2E Test Results](#7-federation-e2e-test-results)
8. [Deployment & Operations](#8-deployment--operations)
9. [What the Website Needs to Explain](#9-what-the-website-needs-to-explain)
10. [Updated Test Counts](#10-updated-test-counts)
11. [Production URLs](#11-production-urls)
12. [Action Items for Protocol Team](#12-action-items-for-protocol-team)

---

## 1. The Tezit Relay Node

### What It Is

The **tezit-relay** is a self-contained, self-hostable messaging node that implements the Tezit Protocol's messaging profile. It runs on its own dedicated infrastructure and handles:

- **Teams** — create, manage, add members
- **Contacts** — register with tezAddress (user@host format)
- **Messaging** — share tezits with context layers, threading, replies
- **Conversations** — DMs, group conversations, unread tracking
- **Federation** — send/receive tezits between relay nodes via Ed25519-signed HTTP
- **Audit trail** — every action logged

### Why It's Separate

The relay is **not** part of MyPA. It is a standalone service that MyPA (and any other Tezit implementer) connects to as a client. This means:

- **Any platform can run a relay node** — not just MyPA
- **Teams on different nodes can communicate** via federation
- **The relay owns the messaging data** — implementers are adapter layers
- **Self-hostable** — organizations can run their own node ($4/month DigitalOcean droplet)

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Node.js 22 (ESM) |
| Framework | Express + TypeScript |
| Database | SQLite + Drizzle ORM (WAL mode) |
| Auth | JWT (jose library, `sub` claim required) |
| Process | PM2 (fork mode, single instance for SQLite safety) |
| Federation | Ed25519 (Node.js crypto), HTTP signatures |

### Database Schema (12 tables)

| Table | Purpose |
|-------|---------|
| `contacts` | User profiles with tezAddress (`userId@relayHost`) |
| `teams` | Team definitions |
| `team_members` | Team membership with roles |
| `tez` | Messages with surface text, type, urgency, visibility |
| `tez_context` | Context layers (background, fact, artifact, relationship, constraint, hint) |
| `tez_recipients` | Per-message delivery tracking |
| `conversations` | DM and group conversations |
| `conversation_members` | Conversation membership with read tracking |
| `audit_log` | Full audit trail (team-scoped) |
| `federated_servers` | Known federation peers with trust levels |
| `federated_tez` | Mapping between local and remote tez IDs |
| `federation_outbox` | Outbound federation queue with retry scheduling |

### Source Code

**Repo:** [github.com/ragurob/tezit-relay](https://github.com/ragurob/tezit-relay)

```
tezit-relay/
├── src/
│   ├── routes/
│   │   ├── tez.ts              # Share, reply, stream, get, thread
│   │   ├── teams.ts            # CRUD + membership
│   │   ├── contacts.ts         # Register, search, profile
│   │   ├── conversations.ts    # DM, group, unread counts
│   │   ├── federation.ts       # Inbox, server-info, verify
│   │   ├── events.ts           # Health endpoint
│   │   └── admin.ts            # Admin operations
│   ├── services/
│   │   ├── identity.ts         # Ed25519 keypair management
│   │   ├── httpSignature.ts    # Sign/verify HTTP requests
│   │   ├── federationBundle.ts # Bundle format + hash integrity
│   │   ├── federationOutbound.ts # Routing + retry queue
│   │   ├── discovery.ts        # .well-known/tezit.json client
│   │   ├── acl.ts              # Access control
│   │   └── audit.ts            # Audit logging
│   ├── middleware/
│   │   └── auth.ts             # JWT verification (sub claim)
│   ├── db/
│   │   └── schema.ts           # Drizzle ORM schema (12 tables)
│   └── config.ts               # Environment configuration
├── deploy/
│   ├── provision.sh            # One-time server setup
│   ├── deploy.sh               # Build + deploy
│   ├── nginx-relay.conf        # Rate-limited reverse proxy
│   ├── ecosystem.config.cjs    # PM2 configuration
│   ├── health-monitor.sh       # Cron-based health + auto-restart
│   ├── litestream.yml          # Continuous SQLite backup config
│   ├── litestream-setup.sh     # Backup service setup
│   ├── ssl-setup.sh            # Let's Encrypt automation
│   └── restore-from-backup.sh  # Disaster recovery
└── tests/                      # 7 test suites, 179+ tests
```

---

## 2. Federation System

### Overview

Federation allows tezit-relay nodes to exchange messages across server boundaries. When a user on `relay-a.example.com` sends a tez to a recipient on `relay-b.example.com`, the message travels via signed HTTP POST.

### Identity

Each relay node generates a permanent **Ed25519 keypair** on first start:

```
Files: DATA_DIR/server.pub (Base64 DER public key)
       DATA_DIR/server.key (PEM PKCS8 private key)

ServerId: First 16 hex chars of SHA-256(publicKeyBase64)
Example:  e4c0106bf422491e
```

The identity is published at `/.well-known/tezit.json`:

```json
{
  "host": "relay.tezit.com",
  "server_id": "e4c0106bf422491e",
  "public_key": "MCowBQYDK2VwAyEAc2hnSV2eLRcvVCdIsYZLiZACB+yxpr4PK7I5sZ++Amc=",
  "protocol_version": "1.2.4",
  "profiles": ["messaging", "knowledge"],
  "federation": {
    "enabled": true,
    "mode": "allowlist",
    "inbox": "/federation/inbox"
  }
}
```

### HTTP Signatures (Simplified RFC 9421)

Every federation request is cryptographically signed:

**Signed components:**
- `(request-target)` — method + path (lowercased)
- `host` — destination host
- `date` — UTC RFC2822 timestamp (must be within 5 minutes)
- `digest` — SHA-256 of request body

**Headers added to request:**
```
Host: relay-b.example.com
Date: Mon, 10 Feb 2026 15:30:00 GMT
Digest: SHA-256=<base64-encoded-hash>
Signature: <base64-encoded-Ed25519-signature>
Signature-Input: keyId="e4c0106bf422491e",headers="(request-target) host date digest",algorithm="ed25519"
```

**Verification:** Receiving server reconstructs the signing string from headers, verifies with sender's public key (fetched via `.well-known/tezit.json` discovery).

### Federation Bundle Format

```json
{
  "protocol_version": "1.2.4",
  "bundle_type": "federation_delivery",
  "sender_server": "relay-a.example.com",
  "sender_server_id": "e4c0106bf422491e",
  "from": "alice@relay-a.example.com",
  "to": ["bob@relay-b.example.com"],
  "tez": {
    "id": "uuid",
    "threadId": null,
    "parentTezId": null,
    "surfaceText": "Q4 budget needs review",
    "type": "decision",
    "urgency": "high",
    "actionRequested": "Please approve by Friday",
    "visibility": "team",
    "createdAt": "2026-02-10T15:30:00.000Z"
  },
  "context": [
    {
      "layer": "background",
      "content": "Full budget spreadsheet analysis...",
      "mimeType": "text/plain",
      "confidence": 95,
      "source": "verified"
    }
  ],
  "bundle_hash": "sha256-hex-of-deterministic-json",
  "signed_at": "2026-02-10T15:30:00.000Z"
}
```

**Integrity:** `bundle_hash` is SHA-256 of deterministically serialized `{tez, context}` (sorted keys). Receiving server recomputes and verifies.

### Trust Model

| Trust Level | Description | Behavior |
|-------------|-------------|----------|
| `pending` | Newly discovered server | Rejected in allowlist mode, accepted in open mode |
| `trusted` | Explicitly approved | Tezits accepted and delivered |
| `blocked` | Explicitly denied | All deliveries rejected |

**Federation modes:**
- **`allowlist`** (default) — Only servers with `trustLevel: "trusted"` can deliver. New servers start as `pending` and require admin approval.
- **`open`** — Any server can deliver. Useful for development and public relays.

### Discovery Flow

1. User sends tez to `bob@relay-b.example.com`
2. Relay partitions recipients: local vs remote (by host)
3. For remote: fetch `https://relay-b.example.com/.well-known/tezit.json` (cached 1 hour)
4. Check if `relay-b.example.com` is trusted
5. Build federation bundle with context layers
6. Compute bundle hash (SHA-256)
7. Sign HTTP request with Ed25519 private key
8. POST to `https://relay-b.example.com/federation/inbox`
9. On success: record in `federated_tez`, audit as `federation.sent`
10. On failure: queue in `federation_outbox` for retry

### Retry Queue (Exponential Backoff)

| Attempt | Delay |
|---------|-------|
| 1 | 1 minute |
| 2 | 5 minutes |
| 3 | 30 minutes |
| 4 | 2 hours |
| 5 | 12 hours |

After 5 failed attempts: status changes to `expired`, audit logged as `federation.failed`.

### Federation Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/federation/inbox` | HTTP Signature | Receive federated tez |
| GET | `/federation/server-info` | None | Public server identity |
| POST | `/federation/verify` | None | Trust handshake |
| GET | `/.well-known/tezit.json` | None | Protocol discovery |

### Tez Addressing

Every user gets a **tezAddress** on registration: `{userId}@{relayHost}`

Example: `user-abc123@relay.tezit.com`

This is the canonical address for federation routing. The `@host` suffix determines which relay node to deliver to.

---

## 3. Infrastructure Map

### Production Topology

```
                                  ┌──────────────────────┐
                                  │   relay.tezit.com    │
                                  │   174.138.80.70      │
                                  │   (dedicated droplet) │
                                  │                      │
                                  │  tezit-relay :3002   │
                                  │  SQLite + Federation │
                                  │  Ed25519 identity    │
                                  └──────────┬───────────┘
                                             │
                               VPC: 10.108.0.0/20
                                             │
┌─────────────────────────────┐              │
│     app.mypa.chat           │              │
│     164.90.135.75           ├──────────────┘
│     (main droplet)          │  10.108.0.2 ←→ 10.108.0.3
│                             │
│  nginx:                     │
│    /api/*  → mypa-api:3001  │
│    /relay/* → relay:3002    │   (VPC private IP)
│    /v1/*   → gateway:18789  │
│                             │
│  PM2:                       │
│    mypa-api    :3001        │
│    pa-workspace:3003        │
│                             │
│  OpenClaw Gateway :18789    │
└─────────────────────────────┘

┌─────────────────────────────┐
│  Other federation nodes     │
│  (future)                   │
│                             │
│  Any org can run their own  │
│  tezit-relay and federate   │
│  with relay.tezit.com       │
└─────────────────────────────┘
```

### Two Droplets

| Droplet | IP | VPC IP | Cost | Purpose |
|---------|----|---------|----|---------|
| mypa-prod-01 | 164.90.135.75 | 10.108.0.3 | ~$12/mo | MyPA app + API + Gateway |
| tezit-relay | 174.138.80.70 | 10.108.0.2 | $4/mo | Dedicated relay node |

Both on DigitalOcean NYC3 in the same VPC (10.108.0.0/20). Inter-droplet traffic travels over private network, never public internet.

### Domains

| Domain | Points To | Purpose |
|--------|-----------|---------|
| app.mypa.chat | 164.90.135.75 | Unified PWA + API |
| oc.mypa.chat | 164.90.135.75 | OpenClaw Gateway + Canvas |
| relay.tezit.com | 174.138.80.70 | Tezit Relay node (federation) |

### Security

| Layer | Protection |
|-------|-----------|
| **Firewall (UFW)** | SSH + 80 + 443 only (relay droplet) |
| **VPC** | Inter-droplet on private network (port 3002 allowed from VPC only) |
| **nginx** | Rate limiting: 10r/s general, 5r/s writes, 2r/s federation |
| **PM2** | Per-service Unix users (svc-relay, svc-mypa, svc-paworkspace) |
| **TLS** | Let's Encrypt certificates on all domains |
| **Auth** | JWT with shared secret, `sub` claim required |
| **Federation** | Ed25519 signatures, 5-minute time window, SHA-256 digest |

---

## 4. Adapter Architecture

### How MyPA Connects to the Relay

MyPA backend is now an **adapter layer** — it preserves all existing API contracts while delegating messaging to the relay as canonical store.

```
Frontend (unchanged) → MyPA API (adapter) → tezit-relay (canonical store)
                                          → local shadow DB (MyPA-specific fields)
```

### Key Components

**relayClient.ts** — HTTP client wrapping relay API:
- `shareTez()` — Forward card creation to relay
- `getStream()` — Fetch feed from relay
- `getTez()` — Get single tez
- `getThread()` — Get thread
- `createRelayTeam()` — Sync team creation
- `addRelayTeamMember()` — Sync member addition
- `registerRelayContact()` — Register user as relay contact
- 5-second timeout, JWT forwarding, graceful null-return on failure

**relayMapper.ts** — Bidirectional field mapping:
- `cardToRelayShare()` — MyPA card params → relay ShareSchema
- `relayTezToCard()` — Relay tez response → MyPA card shape

### Feature Flag

```env
RELAY_ENABLED=true   # Activates dual-write to relay
RELAY_URL=http://10.108.0.2:3002  # VPC private IP
```

When `RELAY_ENABLED=false`, MyPA works standalone with local DB only. No relay dependency.

### Dual-Write Flow

1. User creates card in MyPA
2. MyPA generates UUID
3. Writes to relay via `relayClient.shareTez()` (fire-and-forget)
4. Writes to local `cards` table (shadow, for MyPA-specific fields)
5. Writes to `card_context` + FTS5 (Library preservation)
6. If relay fails: local write succeeds, warning logged

---

## 5. Orchestrated Registration

When a new user registers on MyPA, the system automatically:

1. Creates MyPA user account (local DB)
2. Registers relay contact (`POST /contacts/register` on relay)
3. Creates default team in relay
4. Syncs team membership

This is fire-and-forget — if the relay is unavailable, MyPA registration succeeds and relay sync happens later.

**Admin endpoint on relay:** `POST /contacts/admin/upsert` — server-to-server sync using `RELAY_SYNC_TOKEN` (not user JWT). This allows MyPA to create relay contacts on behalf of users during registration.

---

## 6. Real-Time Messaging (SSE)

**Note:** SSE is implemented in the **MyPA backend**, not in the relay itself. The relay is currently pull-based (clients poll `/tez/stream`).

### MyPA SSE Implementation

| Component | Description |
|-----------|-------------|
| **Endpoint** | `GET /events/subscribe?token=<jwt>` |
| **Protocol** | Server-Sent Events (text/event-stream) |
| **Heartbeat** | Every 30 seconds (keeps connection alive) |
| **Events** | `new_tez`, `unread_update`, `new_message` |
| **EventBus** | User-scoped pub/sub (in-memory) |

### Canvas Consumer

The Tezit Messenger Canvas UI uses SSE with auto-reconnect:
- Primary: EventSource connection (60-second reconnect on failure)
- Fallback: 10-second polling when SSE unavailable
- Adaptive: switches between SSE and polling based on connectivity

### nginx Requirements

For SSE to work through nginx reverse proxy:
```nginx
proxy_buffering off;
proxy_read_timeout 86400s;
proxy_cache off;
```

---

## 7. Federation E2E Test Results

### 50 Federation Tests Passing (tezit-relay)

The federation test suite covers:

**Identity & Cryptography:**
- Ed25519 keypair generation and persistence
- Deterministic serverId derivation from public key
- HTTP signature sign/verify roundtrip
- Signature tampering detection (body, date, path)
- Date validation (reject requests >5 minutes old)

**Bundle Integrity:**
- Federation bundle format validation
- SHA-256 hash computation and verification
- Deterministic JSON serialization (sorted keys)
- Bundle with/without context layers

**Trust & Discovery:**
- Trust handshake (POST /federation/verify)
- Allowlist mode: reject untrusted servers
- Open mode: accept any server
- Server info endpoint (GET /federation/server-info)
- .well-known/tezit.json discovery

**Delivery:**
- Inbound federation delivery (POST /federation/inbox)
- Partial delivery (207 Multi-Status when some recipients not found)
- Thread reconstruction on federated tezits
- Outbound routing and queue management
- Retry scheduling with exponential backoff

### 179+ Total Relay Tests Passing

| Test Suite | Tests |
|------------|-------|
| tez.test.ts | Core sharing, reply, stream, threading |
| teams.test.ts | CRUD, membership, roles |
| contacts.test.ts | Registration, search, profiles |
| conversations.test.ts | DM, group, unread counts |
| dm-isolation.test.ts | Cross-user isolation |
| audit.test.ts | Audit logging |
| federation.test.ts | All federation tests above |

### Production E2E Verification

All verified against production at relay.tezit.com:

```
✅ Register contact → tezAddress assigned
✅ Create team → relay team created
✅ Send Tez with 3 context layers (background, fact, constraint)
✅ Retrieve Tez with full context iceberg
✅ Reply (threading) with additional context
✅ Get thread (2+ messages)
✅ Team stream with pagination
✅ Contact search
✅ DM creation and messaging
✅ Unread counts (per-team + per-conversation)
✅ Add member to team
✅ Federation discovery (/.well-known/tezit.json)
✅ Health check → OK
```

---

## 8. Deployment & Operations

### Deploy Scripts

All in `tezit-relay/deploy/`:

| Script | Purpose |
|--------|---------|
| `provision.sh` | One-time server setup: Node.js, PM2, UFW, Litestream, service user |
| `deploy.sh` | Build locally, rsync to server, npm ci, schema push, PM2 restart, health check |
| `nginx-relay.conf` | Rate-limited reverse proxy (3 zones) |
| `ecosystem.config.cjs` | PM2 config: fork mode, 256MB max, svc-relay user |
| `health-monitor.sh` | Cron (every 5 min): 3 retries, auto-restart, ntfy alert |
| `ssl-setup.sh` | Let's Encrypt via certbot |
| `litestream.yml` | Continuous SQLite backup: 10s sync, 24h snapshots, 30-day retention |
| `litestream-setup.sh` | Configure Litestream systemd service |
| `restore-from-backup.sh` | Disaster recovery from Litestream backup |

### Provisioning a New Node

```bash
# 1. Create $4/month droplet (DigitalOcean, Ubuntu 24.04)
doctl compute droplet create my-relay \
  --region nyc3 --size s-1vcpu-512mb-10gb \
  --image ubuntu-24-04-x64

# 2. Run provision script
scp deploy/provision.sh root@<IP>:/tmp/
ssh root@<IP> bash /tmp/provision.sh

# 3. Set environment
ssh root@<IP>
cat > /var/tezit-relay/app/.env << 'EOF'
JWT_SECRET=your-shared-secret
RELAY_HOST=your-domain.com
FEDERATION_ENABLED=true
FEDERATION_MODE=allowlist
DATA_DIR=/var/tezit-relay/data
NODE_ENV=production
PORT=3002
EOF

# 4. Deploy code
./deploy/deploy.sh

# 5. SSL
./deploy/ssl-setup.sh your-domain.com
```

### Health Monitoring

- Cron: `*/5 * * * * /var/tezit-relay/app/deploy/health-monitor.sh`
- 3 health check retries before action
- Auto-restart PM2 on failure
- ntfy.sh alert if restart fails (configurable via `NTFY_TOPIC`)

### Backup (Litestream)

- **Continuous replication** to DigitalOcean Spaces (S3-compatible)
- 10-second sync interval
- 24-hour snapshot frequency
- 30-day retention
- Restore: `deploy/restore-from-backup.sh`

**Status:** Litestream installed, config ready. Waiting for Spaces API keys to activate.

---

## 9. What the Website Needs to Explain

### New Concepts for tezit.com

The website currently explains tezits as knowledge artifacts. It now needs to also explain:

#### 9.1 Relay Nodes

**Key message:** "Tezit is not a platform. It's a protocol with self-hostable nodes."

- A **Tezit Relay** is a lightweight server that stores and routes tezits
- Anyone can run their own relay (starts at $4/month)
- Your organization's tezits live on YOUR infrastructure
- The relay handles teams, contacts, messaging, threading, and context layers

#### 9.2 Federation

**Key message:** "Tezit nodes talk to each other. Your team can message any team on any node."

- Relay nodes discover each other via `.well-known/tezit.json`
- Messages are cryptographically signed (Ed25519) — tamper-proof
- Trust is explicit (allowlist or open mode)
- Context layers travel with the message — the recipient's relay has the full iceberg
- Failed deliveries retry automatically (exponential backoff)

#### 9.3 Tez Addresses

**Key message:** "Your tezAddress is like an email address for context-rich messaging."

- Format: `user@relay-host` (e.g., `alice@relay.company.com`)
- Determined by which relay node you register on
- Used for cross-node addressing in federation

#### 9.4 The Node + Platform Distinction

**Key message:** "MyPA is to Tezit what Gmail is to email."

- **tezit-relay** is the open-source node (like an email server)
- **MyPA.chat** is one client that uses the relay (like Gmail uses SMTP)
- Other platforms can build their own clients on top of any relay
- The relay is self-hostable — bring your own infrastructure

#### 9.5 Suggested Website Sections

1. **"Run Your Own Node"** — Quick start guide for deploying tezit-relay
   - DigitalOcean one-click? (future)
   - Docker compose? (future)
   - For now: provision.sh script + deploy guide

2. **"Federation"** — How nodes communicate
   - Discovery protocol (.well-known/tezit.json)
   - Trust model (allowlist vs open)
   - Bundle format and integrity
   - Retry and reliability

3. **"For Organizations"** — Self-hosting pitch
   - Data sovereignty (your tezits on your server)
   - Federation with partners (cross-org messaging)
   - Audit trail (every action logged)
   - Cost: $4-12/month depending on scale

4. **"Architecture"** — Technical overview
   - Protocol + Node + Client distinction
   - How federation works (diagram)
   - Context layer model
   - Cryptographic signing

---

## 10. Updated Test Counts

| Service | Tests | Notes |
|---------|-------|-------|
| MyPA backend | 639 passing + 1 skipped | Includes 21 new relay adapter tests |
| tezit-relay | 179+ passing | Includes 50 federation tests |
| pa-workspace | 138 passing | Google Workspace integration |
| **Total** | **957+ tests** | Across 3 services |

---

## 11. Production URLs

| URL | Purpose | Auth |
|-----|---------|------|
| https://app.mypa.chat | MyPA PWA + API | JWT Bearer |
| https://oc.mypa.chat | OpenClaw Gateway + Canvas UI | Gateway token |
| https://relay.tezit.com | Tezit Relay node | JWT Bearer |
| https://relay.tezit.com/.well-known/tezit.json | Federation discovery | None |
| https://relay.tezit.com/health | Health check | None |
| https://relay.tezit.com/federation/server-info | Public identity | None |

### Test Credentials

```
Email:    test@test.com
Password: testtest1
```

Login via `POST https://app.mypa.chat/api/auth/login` — returns JWT with `sub` claim that works on both MyPA API and relay.

---

## 12. Action Items for Protocol Team

### Must Do (for website/spec)

1. **Add "Nodes & Federation" section to spec** — The protocol now has a working federation implementation. The spec should document:
   - `.well-known/tezit.json` discovery format
   - Federation bundle format
   - HTTP signature scheme
   - Trust model (allowlist/open)
   - Retry semantics

2. **Update Known Implementers table** — MyPA entry should mention:
   - Dedicated relay node (relay.tezit.com)
   - Live federation with Ed25519 signing
   - 957+ automated tests across 3 services

3. **Add relay as reference implementation** — Link to `github.com/ragurob/tezit-relay` as the reference relay node implementation

4. **Create "Run Your Own Node" guide** — Based on our deploy scripts, create a quickstart for self-hosting

### Should Do (for protocol evolution)

5. **Formalize federation in spec v1.3** — Our implementation can serve as the reference for a federation section in the protocol spec

6. **Add federation bundle to JSON schemas** — Create `schemas/federation-bundle.json` for validation

7. **Add tezAddress format to spec** — `user@host` format for cross-node addressing

8. **Consider SSE in relay** — Currently pull-based. Real-time events would improve UX for direct relay clients.

### Nice to Have

9. **Docker image for relay** — Lower barrier to self-hosting
10. **Federation test fixtures** — Add to `test-bundles/` for implementers to validate against
11. **Admin UI for federation** — Manage trust levels, view outbox, monitor health

---

## Appendix: Configuration Reference

### Relay Environment Variables

```env
# Required
JWT_SECRET=<shared-with-your-auth-system>
RELAY_HOST=relay.yourdomain.com
DATA_DIR=/var/tezit-relay/data

# Federation
FEDERATION_ENABLED=true
FEDERATION_MODE=allowlist    # or "open"

# Optional
PORT=3002                    # Default: 3002
NODE_ENV=production
MAX_TEZ_SIZE_BYTES=1048576   # Default: 1MB
MAX_CONTEXT_ITEMS=50         # Default: 50
MAX_RECIPIENTS=100           # Default: 100
ADMIN_USER_IDS=user1,user2   # Comma-separated admin user IDs

# Sync (for orchestrated registration from platform)
RELAY_SYNC_TOKEN=<server-to-server-admin-token>
```

### MyPA Environment Variables (relay integration)

```env
RELAY_ENABLED=true
RELAY_URL=http://10.108.0.2:3002   # VPC private IP (or public URL)
RELAY_SYNC_TOKEN=<matches-relay-side>
```

---

**Document version:** 1.0
**Last updated:** February 10, 2026
**License:** CC-BY-4.0
