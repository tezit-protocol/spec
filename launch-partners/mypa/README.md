# MyPA.chat — Tezit Protocol Launch Partner

**Implementation:** MyPA.chat (https://app.mypa.chat)
**Status:** Production (6+ months)
**Protocol Version:** v1.2.4
**TIP Version:** v1.0.3
**Profiles:** knowledge, messaging, coordination
**Source:** [github.com/ragurob/MyPA.chat](https://github.com/ragurob/MyPA.chat) (monorepo)
**Relay Node:** [github.com/ragurob/tezit-relay](https://github.com/ragurob/tezit-relay) (dedicated)

---

## Overview

MyPA.chat is a production Tezit Protocol implementation with 6+ months of real-world deployment, 957+ automated tests across 3 services, and 100K+ context entries in production.

**As of February 10, 2026:** MyPA operates a **dedicated Tezit Relay node** (relay.tezit.com) with **live federation** using Ed25519 cryptographic signing. The relay is a standalone, self-hostable service that any Tezit implementer can use.

**Architecture:** Three services + Canvas UI, powered by OpenClaw (AI runtime):
- **backend/** — API server: Tez CRUD, Library (FTS5), TIP interrogation, auth, relay adapter
- **tezit-relay** — Dedicated messaging node: teams, contacts, conversations, threading, context layers, federation
- **pa-workspace/** — Google Workspace: PA email, calendar, drive, Tez email transport
- **tezit-messenger** — Canvas UI: WhatsApp-style UI for teams, DMs, context

**Key capabilities:**
- Full TIP interrogation with citation verification
- FTS5 Discovery Protocol (sub-10ms at 100K+ entries)
- Fork semantics (counter, extension, reframe, update)
- Email transport (Tez via email with protocol headers)
- Multi-layer prompt injection defense
- Engagement scoring (interrogation-weighted)
- **Live federation** with Ed25519 signing, HTTP signatures, and .well-known/tezit.json discovery
- **Dedicated relay node** on its own infrastructure (self-hostable for $4/month)
- **Orchestrated registration** (user signup auto-provisions relay contact + team)
- **Real-time messaging** via SSE with EventBus pub/sub

---

## Documents in This Directory

### [INFRASTRUCTURE_UPDATE.md](./INFRASTRUCTURE_UPDATE.md) (NEW — Feb 10, 2026)
Comprehensive transfer document covering the dedicated relay node, live federation system, infrastructure map, adapter architecture, deployment model, and what the website needs to explain about nodes and federation. **Start here for the latest.**

### [CONTRIBUTION_OFFER.md](./CONTRIBUTION_OFFER.md)
Formal contribution offer to the Tezit ecosystem: new spec proposals (public TIP endpoints, email transport, discovery protocol), reference implementations, answers to TheAICoder's open questions, and interoperability testing.

### [PRODUCTION_LEARNINGS.md](./PRODUCTION_LEARNINGS.md)
Comprehensive learnings from 6+ months of production deployment covering discovery at scale, security and prompt injection defense, protocol extensions, and operational lessons.

### [CONFORMANCE_MATRIX.md](./CONFORMANCE_MATRIX.md)
Detailed conformance to Tezit Protocol v1.2.4 and TIP v1.0.3 specifications.

### [PROTOCOL_PROPOSALS.md](./PROTOCOL_PROPOSALS.md)
Seven specific proposals for Tezit Protocol v1.3 based on production experience: discovery protocol, security guidelines, email transport, fork semantics, engagement metadata, mirror distinction, and reference test fixtures.

---

## Production URLs

| URL | Purpose |
|-----|---------|
| https://app.mypa.chat | MyPA PWA + API |
| https://oc.mypa.chat | OpenClaw Gateway + Canvas UI |
| https://relay.tezit.com | Tezit Relay node (federation) |
| https://relay.tezit.com/.well-known/tezit.json | Federation discovery |
| https://relay.tezit.com/federation/server-info | Public node identity |
| https://relay.tezit.com/health | Relay health check |

---

## Test Credentials (Production)

```
Email:    test@test.com
Password: testtest1
```

Available for other Tezit Protocol implementers to test interoperability.

Login: `POST https://app.mypa.chat/api/auth/login` — returns JWT with `sub` claim, works on both MyPA API and relay.

---

## Test Coverage

| Service | Tests | Notes |
|---------|-------|-------|
| MyPA backend | 639 + 1 skipped | Includes 21 relay adapter tests |
| tezit-relay | 179+ | Includes 50 federation tests |
| pa-workspace | 138 | Google Workspace integration |
| **Total** | **957+** | Across 3 services |

---

## Contact

**Repositories:**
- [github.com/ragurob/MyPA.chat](https://github.com/ragurob/MyPA.chat) — MyPA monorepo
- [github.com/ragurob/tezit-relay](https://github.com/ragurob/tezit-relay) — Relay node
- [github.com/ragurob/tezit-messenger](https://github.com/ragurob/tezit-messenger) — Canvas UI

**Available for:** Questions, collaboration, interoperability testing, federation testing, code review
