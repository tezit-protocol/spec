# Tezit Launch Partner Update (TheAICoderV2)

Date: 2026-02-06

## Executive Summary

TheAICoderV2 is implementing **Tezit Protocol v1.2** by making **Tez bundles** the canonical, portable artifact for AI coding work.

What we ship today:

- **Portable `.tez` export** (ZIP archive with `manifest.json` + `context/` + synthesis) with SHA-256 hashes for context items
- **Hosted bundle storage** in Postgres (bundle metadata, context items, share links, interrogation sessions)
- **TIP Lite interrogation** (answers grounded in bundle context only, mandatory citations, abstention) with **SSE streaming**
- **Spec-compatible `/api/v1/tez/*` endpoints** (owner-only MVP for now)
- **`.tez` import MVP**: upload archive, validate manifest, persist bundle + items, enable interrogation
- **Forking + lineage endpoints** (owner-only MVP for now)
- **TIP streaming taxonomy on `/api/v1`**: emits `tip.*` SSE events (minimal mapping for TIP Lite)
- **Canonical `tez://...` URIs** for bundles
- **Platform discovery** at `GET /.well-known/tezit.json`

What we have not shipped yet (interop backlog):

- Versioning endpoints (`/versions`) and diffs
- Share-scoped access control for `/api/v1` endpoints (currently owner-only)
- TIP Enterprise addendum features that require retrieval (retrieval transparency, multi-pass retrieval)
- Extensions like signing/encryption

---

## What We've Implemented (Code References)

### 1) Tez Bundle Data Model (DB)

- Schema: `src/lib/db/schema/tezit.ts`
- Tables:
  - `tez_bundles`
  - `tez_context_items`
  - `tez_interrogation_sessions`
  - `tez_interrogation_queries`
  - `tez_shares`

### 2) Manifest + Types (Tezit v1.2)

- Types: `src/lib/tezit/types.ts`
- Manifest creation + Zod validation: `src/lib/tezit/manifest.ts`

### 3) Tez URI Support

- Parse/build/resolve `tez://...`: `src/lib/tezit/uri.ts`

### 4) TIP Lite Interrogation

- TIP prompt construction + citation parsing + classification + validation:
  - `src/lib/tezit/interrogation.ts`
- TIP Lite pipeline (context loaded into prompt; no retrieval):
  - `src/lib/services/interrogation-service.ts`

### 5) Session -> Tez Export and `.tez` Download

- Export service + packaging as ZIP (`.tez`): `src/lib/services/tezit-service.ts`
- Export endpoints:
  - `POST /api/sessions/{sessionId}/export`: `src/app/api/sessions/[id]/export/route.ts`
  - `GET /api/sessions/{sessionId}/export/download`: `src/app/api/sessions/[id]/export/download/route.ts`

### 6) Interrogation Endpoints

- `POST /api/tez/{bundleId}/interrogate`: `src/app/api/tez/[id]/interrogate/route.ts`
- `POST /api/tez/{bundleId}/interrogate/stream` (SSE): `src/app/api/tez/[id]/interrogate/stream/route.ts`
- Session management:
  - `GET /api/tez/{bundleId}/interrogate/sessions`
  - `GET /api/tez/{bundleId}/interrogate/sessions/{sessionId}`
  - `DELETE /api/tez/{bundleId}/interrogate/sessions/{sessionId}`

### 7) Discovery Document

- `GET /.well-known/tezit.json`: `src/app/.well-known/tezit.json/route.ts`

### 8) Spec-Compatible HTTP API (`/api/v1/tez/*`) + Import

- Base paths:
  - `GET /api/v1/tez`
  - `GET /api/v1/tez/{id}`
  - `GET /api/v1/tez/{id}/synthesis`
  - `GET /api/v1/tez/{id}/context`
  - `GET /api/v1/tez/{id}/context/{itemId}`
  - `GET /api/v1/tez/{id}/archive`
  - `POST /api/v1/tez/{id}/interrogate`
  - `POST /api/v1/tez/{id}/interrogate/stream`
- `.tez` import:
  - `POST /api/v1/tez/import`

### 9) Forking + Lineage (v1)

- `POST /api/v1/tez/{id}/fork`
- `GET /api/v1/tez/{id}/forks`
- `GET /api/v1/tez/{id}/lineage`

Note: these are currently **owner-only** while we wire share-scoped permissions.

---

## How We're Using Tezit (Product Integration)

- **Code Review Profile**: AI coding sessions export as `code_review` Tez bundles with context items representing prompts, AI responses, code changes, terminal output, and errors.
- **TIP**: Anyone with access to the bundle can interrogate it with grounding + citations, enabling community trust and auditability.
- **Artifacts as evidence**: Tez bundles are designed to become evidence attachments for proposals/votes/imports/marketplace listings as those features ship.

---

## Proposed Interop Milestones (Next)

1. **Versioning endpoints**: `/api/v1/tez/{id}/versions` and point-in-time fetches.
2. **Share-scoped `/api/v1` access**: allow Tezit clients to use share tokens instead of owner-only auth.
3. **TIP Enterprise addendum (retrieval-dependent)**: retrieval transparency + multi-pass retrieval strategies once we introduce retrieval.
4. **Extensions**: facts/relationships and optional signing/encryption.
