# MyPA - Tezit Protocol Launch Partner

**Implementation:** MyPA (https://app.mypa.chat)
**Status:** Production (6+ months)
**Protocol Version:** v1.2.4
**TIP Version:** v1.0.3
**Profiles:** knowledge, messaging, coordination

---

## Overview

MyPA is a production Tezit Protocol implementation with 6+ months of real-world experience, 544 automated tests, and 100K+ context entries in production.

**Key Contributions:**
- ✅ **Tez Discovery Protocol** - Reference implementation for navigating 100K+ tezits
- ✅ **Security Guidelines** - Prompt injection defense and TIP citation verification
- ✅ **Protocol Extensions** - Email transport, fork semantics, engagement signals
- ✅ **Production Metrics** - Performance benchmarks and operational lessons

---

## Implementation Details

**Stack:**
- Backend: Express + TypeScript + Drizzle ORM + SQLite
- Frontend: React 18 + Vite + TypeScript + TailwindCSS
- AI: OpenClaw Runtime (Claude Sonnet 4.5)
- Search: SQLite FTS5 with Porter stemming
- Testing: Vitest (544 tests, 21 test files)

**Production Characteristics:**
- Database: ~500MB at 25K context entries
- Search Index: ~50MB FTS5 (10% overhead)
- Query Latency: p99 <10ms for search, <2ms for ID lookups
- Scale: Handles 100K+ entries with sub-millisecond queries

---

## Documents in This Directory

### [PRODUCTION_LEARNINGS.md](./PRODUCTION_LEARNINGS.md)
Comprehensive learnings from 6+ months of production deployment covering:
- Tez Discovery at Scale (FTS5, engagement scoring, browse mode)
- Security & Prompt Injection (multi-layer defense, TIP security)
- Protocol Extensions (email transport, fork semantics, mirrors)
- Operational Lessons (database architecture, testing, CI/CD)

### [CONFORMANCE_MATRIX.md](./CONFORMANCE_MATRIX.md)
Detailed conformance to Tezit Protocol v1.2.4 and TIP v1.0.3 specifications.

### [PROTOCOL_PROPOSALS.md](./PROTOCOL_PROPOSALS.md)
Specific proposals for Tezit Protocol v1.3 based on production experience.

---

## Production URLs

- **Production App:** https://app.mypa.chat
- **API Health:** https://app.mypa.chat/health
- **Source Code:** https://github.com/ragurob/tezmob (MIT License)
- **Protocol Discovery:** https://app.mypa.chat/.well-known/tezit.json

---

## Test User (Production)

```
Email: test@test.com
Password: testtest1
```

Available for Tezit Protocol implementers to test interoperability.

---

## Contact

Available for questions, collaboration, and interoperability testing.

**Repository:** https://github.com/ragurob/tezmob
**Documentation:** See docs/ directory in repo
**Protocol Alignment:** Follows MYPA_ALIGNMENT_GUIDE.md from this spec repo
