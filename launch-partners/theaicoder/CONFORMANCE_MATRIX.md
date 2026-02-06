# Tezit Conformance Matrix (TheAICoderV2)

Date: 2026-02-06

Legend: ✅ implemented, 🟡 partial, ⏳ planned, ❌ not started

This matrix is intentionally conservative: it only claims what exists in this repo today.

---

## Portable Bundle Format (`.tez`)

- ✅ ZIP-based `.tez` export with `manifest.json` + `context/` + synthesis:
  - Code: `src/lib/services/tezit-service.ts`
- ✅ SHA-256 hashes stored for context items:
  - Code: `src/lib/utils/hash`, `src/lib/services/tezit-service.ts`
- ✅ Offline archive contains context files referenced by manifest:
  - Code: `src/lib/services/tezit-service.ts`

## Context Item IDs (Our Convention)

The spec allows arbitrary context item IDs; we use a deterministic scheme for stability across exports and citations:

- ✅ Deterministic IDs: `ctx-000`, `ctx-001`, ... derived from `ordering`
- ✅ Same IDs used across:
  - manifest `context.items[].id`
  - TIP citations (`[[ctx-000]]`)
  - UI mapping from citation -> context item
- Code:
  - `src/lib/services/interrogation-service.ts`
  - `src/lib/services/tezit-service.ts`

## Profiles

- ✅ `code_review` (primary): AI coding sessions export here by default
- ✅ `knowledge` (supported): PRD / receipts exports use `knowledge` where appropriate
- 🟡 `coordination` (types exist; no full product workflow yet)
- ❌ `messaging` (not implemented)

## TIP (Tez Interrogation Protocol)

- ✅ TIP Lite behavior: context-only answers, mandatory citations, abstention
- ✅ Response classification persisted (grounded/inferred/partial/abstention)
- 🟡 SSE streaming interrogation:
  - Partner endpoints: streaming (non-standard event payload)
  - `/api/v1` endpoints: emits `tip.*` event names (minimal TIP Lite mapping)
- ❌ Retrieval (vector/keyword) and retrieval transparency metadata
- ❌ Multi-pass retrieval strategies
- Code:
  - `src/lib/tezit/interrogation.ts`
  - `src/lib/services/interrogation-service.ts`

## URI Scheme

- ✅ `tez://` parser + builder:
  - Code: `src/lib/tezit/uri.ts`

## Discovery (`/.well-known/tezit.json`)

- ✅ Present and public:
  - Code: `src/app/.well-known/tezit.json/route.ts`

## HTTP API Surface (Spec-Compatible Paths)

We ship both:

- **Partner endpoints** under `/api/tez/*` and `/api/sessions/*` (used by the app UI today)
- **Spec paths** under `/api/v1/tez/*` (owner-only MVP for now)

- ✅ `GET /api/v1/tez/{id}`
- ✅ `GET /api/v1/tez/{id}/synthesis`
- ✅ `GET /api/v1/tez/{id}/context`
- ✅ `GET /api/v1/tez/{id}/context/{itemId}`
- ✅ `GET /api/v1/tez/{id}/archive`
- ✅ `POST /api/v1/tez/{id}/interrogate`
- ✅ `POST /api/v1/tez/{id}/interrogate/stream`
- ✅ `POST /api/v1/tez/import` (`.tez` import MVP)
- ✅ Bundle listing (partner): `GET /api/tez`
- ✅ Interrogation (partner): `POST /api/tez/{id}/interrogate`, `POST /api/tez/{id}/interrogate/stream`
- ✅ Share creation (partner): `POST /api/tez/{id}/share`
- ✅ Share consumption page: `GET /tez/share/{token}`

Note: `/api/v1` is currently **owner-only** until share-scoped auth is implemented.

## Forking / Lineage / Versioning

- ✅ Fork endpoints:
  - `POST /api/v1/tez/{id}/fork`
  - `GET /api/v1/tez/{id}/forks`
- ✅ Lineage tree:
  - `GET /api/v1/tez/{id}/lineage`
- ❌ Version listing / diffs:
  - `GET /api/v1/tez/{id}/versions` (planned)

## Security + Governance

- 🟡 Hashes stored; signing/encryption extensions not implemented
- 🟡 Permissions modeled in manifest + DB; enforcement/scoping is minimal today
