# Tezit Launch Partner Follow-Ups (Implementation Backlog)

Date: 2026-02-06

This is the execution backlog for moving from a partner-grade Tezit implementation to broader interoperability.

Legend: ✅ shipped, ⏳ planned

---

## ✅ Shipped (Current)

- ✅ Portable `.tez` export (ZIP archive with `manifest.json` + `context/` + synthesis): `src/lib/services/tezit-service.ts`
- ✅ SHA-256 hashes recorded for context items: `src/lib/utils/hash`, `src/lib/services/tezit-service.ts`
- ✅ Hosted bundle storage (Postgres schema): `src/lib/db/schema/tezit.ts`
- ✅ TIP Lite interrogation (context-only, citations, abstention) with SSE streaming:
  - `src/lib/services/interrogation-service.ts`
  - `POST /api/tez/{id}/interrogate`
  - `POST /api/tez/{id}/interrogate/stream`
- ✅ Canonical `tez://...` URIs: `src/lib/tezit/uri.ts`
- ✅ Public share-link consumption: `GET /tez/share/{token}`
- ✅ Platform discovery: `GET /.well-known/tezit.json`: `src/app/.well-known/tezit.json/route.ts`
- ✅ Spec-compatible HTTP API under `/api/v1/tez/*` (owner-only MVP): `src/app/api/v1/tez/*`
- ✅ `.tez` import MVP: `POST /api/v1/tez/import`
- ✅ Forking + lineage endpoints (owner-only MVP):
  - `POST /api/v1/tez/{id}/fork`
  - `GET /api/v1/tez/{id}/forks`
  - `GET /api/v1/tez/{id}/lineage`
- ✅ TIP streaming taxonomy on `/api/v1` interrogation stream (minimal TIP Lite mapping): emits `tip.*` SSE events

---

## ⏳ Interop v2: Versioning + Share-Scoped Access

Goal: move from owner-only MVP to real third-party interoperability.

Tasks:

- ⏳ Version listing / snapshots:
  - `GET /api/v1/tez/{id}/versions`
  - `GET /api/v1/tez/{id}/versions/{version}`
- ⏳ Share-scoped authorization for `/api/v1` endpoints (not just owner auth)
- ⏳ Optional: `tez://` resolution + deep link fragments in UI

---

## ⏳ TIP Enterprise Addendum (When Retrieval Is Introduced)

We currently run TIP Lite (full context in prompt). When we introduce retrieval, we should add:

- ⏳ Retrieval transparency metadata
- ⏳ Multi-pass retrieval strategies (optional)

---

## ⏳ Extensions (Longer-Term)

- ⏳ Facts extraction extension
- ⏳ Relationships extension
- ⏳ Signing / encryption support

---

## Partner Comms Follow-Ups

- ⏳ Share a sample `.tez` file with Tezit team for interop testing
- ⏳ Confirm endpoint/field expectations for versioning and share-scoped `/api/v1` auth
