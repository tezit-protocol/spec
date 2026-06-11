# Ragu — Tezit Protocol Launch Partner

**Implementation:** Ragu (enterprise AI platform — multi-tenant RAG, assistants, agent orchestration)
**Status:** Production (private deployment)
**Protocol Version:** v1.2
**TIP Version:** v1.0
**Profiles:** knowledge (production), code_review + coordination (authored companion specs)
**Surfaces:** HTTP API (26 tez routes incl. TIP interrogation with SSE streaming), Python SDK (28-operation lifecycle), CLI, MCP tool module (10-tool knowledge core loop)

---

## Overview

Ragu is the first enterprise integration of the Tezit Protocol: tez bundles ride on a multi-tenant platform with fine-grained authorization (relationship-based access control), per-tenant isolation, audited TIP interrogation, and agent-facing bindings (SDK / CLI / MCP). The integration covers the full lifecycle — draft, enrich with context items and conversation, synthesize, publish, interrogate (streaming and non-streaming), reframe, fork, inline export/import, and `.tez` archive exchange.

Ragu previously contributed the Code Review and Coordination companion profiles, the TIP Enterprise Addendum, the proposed extensions for signatures / session transfer / context versioning, and four JSON Schemas now in `schemas/`.

## What this directory contains

- **[PRODUCTION_LEARNINGS.md](./PRODUCTION_LEARNINGS.md)** — protocol-, spec-, and conformance-level lessons from taking the integration to production. The headline: structural conformance can be fully green while the protocol's core promise is silently broken, and the current test bundles cannot detect it. Each lesson links to a filed issue with a concrete proposal.

## Filed from this integration

| Where | What |
|---|---|
| [spec#9](https://github.com/tezit-protocol/spec/issues/9) | Conformance gap: test bundles are passable by synthesis-only implementations — content-only canary queries proposed |
| [spec#10](https://github.com/tezit-protocol/spec/issues/10) | Level 0 inline tez cannot round-trip context evidence — optional embedded content proposed |
| [spec#11](https://github.com/tezit-protocol/spec/issues/11) | TIP citation `verified` needs existence/integrity preconditions (complements [#5](https://github.com/tezit-protocol/spec/issues/5)) |
| [mcp-server#24](https://github.com/tezit-protocol/mcp-server/issues/24) | Reference MCP tool surface: transfer plane vs knowledge core loop, plus agent trust-model lessons |
| spec PR | `schemas/` alignment: code-review schemas vs Code Review Profile v0.2.0 contradictions |
