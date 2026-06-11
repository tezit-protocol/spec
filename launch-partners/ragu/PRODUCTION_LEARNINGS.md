# Tezit Protocol Production Learnings — Ragu Enterprise Integration

**Date:** June 2026
**Implementer:** Ragu (enterprise AI platform)
**Scope:** Protocol v1.2, TIP v1.0, knowledge profile, full HTTP lifecycle + SDK/CLI/MCP bindings
**Audience:** Spec maintainers and implementers

---

## Executive summary

This document captures what an enterprise production integration taught us **about the protocol itself** — not about our platform. Three lessons dominate, each discovered live, each with a spec- or conformance-level consequence:

1. **Structural conformance can be fully green while the protocol's core promise is silently broken.** Our storage layer hashed context content and then dropped the bytes. Manifests validated, counts were right, hashes were recorded, citations could claim `verified` — and interrogation abstained on every fact that lived only in context bytes. Nothing in the current test bundles catches this. → [spec#9](https://github.com/tezit-protocol/spec/issues/9)
2. **The Level 0 inline format cannot transport evidence.** References-only context entries mean a cross-platform inline export → import round-trip preserves the synthesis and loses the context. → [spec#10](https://github.com/tezit-protocol/spec/issues/10)
3. **Citation `verified: true` is currently emittable without retrievable bytes.** Verification needs existence/integrity preconditions anchored to served bytes, beneath the semantic levels proposed in [#5](https://github.com/tezit-protocol/spec/issues/5). → [spec#11](https://github.com/tezit-protocol/spec/issues/11)

Supporting material: a probe methodology that detects all three failure modes ("codeword probe", §4), production budget constants (§5), security-hardening adoption notes confirming the audit log is implementable in a second architecture (§6), and MCP tool-surface feedback ([mcp-server#24](https://github.com/tezit-protocol/mcp-server/issues/24), §7).

A meta-observation up front: **TIP's abstention semantics are what made these defects detectable at all.** Because the protocol requires honest classification (`grounded` vs `abstention`) instead of best-effort answering, a hollow implementation *visibly abstains* rather than plausibly hallucinating. That design choice converted a silent data-loss bug into an observable protocol behavior. It is the strongest part of the spec in practice.

---

## 1. Lesson: the content black hole

### What happened

Our context-item storage path computed the content hash, recorded metadata, and discarded the bytes. Every structural signal stayed green:

- Manifest validated against the schema; `context_item_count` was correct
- Content hashes were present and well-formed (computed from real bytes — then the bytes were dropped)
- Item listings returned complete metadata

Live behavior, before the fix (probe fact present **only** in context bytes):

| Probe | Result |
|---|---|
| `GET .../context-items/{id}/content` | `404 {"detail": "Content not found"}` — always, for every item |
| TIP interrogate: "What is the rollback codeword?" | `classification: partial` — "The context provided does not contain any information about a rollback codeword." |
| Inline export | Frontmatter claimed `context_item_count: 1`, carried zero context refs and no content |

After the fix (durable byte storage, verification re-anchored):

| Probe | Result |
|---|---|
| `GET .../context-items/{id}/content` | `200`, and `sha256(served bytes) == manifest hash` |
| TIP interrogate, same question | `classification: grounded` — "The rollback codeword is MARMALADE-7 [[item-id]]", citation verified against stored bytes |
| Inline export → import | New bundle, context item re-created, bytes identical to source (same sha256 after re-hash) |

### Why the spec should care

The failure mode is *invisible to structure-level validation by construction*: every artifact that schemas can check is derived before the bytes are dropped. Only behavior probes catch it — retrieve the bytes, interrogate a content-only fact, round-trip the bundle. The current interop test bundles do not contain such probes; worse, every fact their grounded queries check for also appears in `tez.md`, so a synthesis-only implementation passes the whole suite ([spec#9](https://github.com/tezit-protocol/spec/issues/9) has the per-query table, verified against current `main`).

### Implementation guidance distilled

- Treat "content bytes retrievable, hash-matching, and interrogable" as the definition of a stored context item; everything else is bookkeeping.
- When feeding stored content to the model, do it through the untrusted-content path (sanitization + delimiter isolation per `docs/security/PROMPT_INJECTION_PREVENTION_2026.md`), with per-item excerpt budgets and an explicit truncation marker; exclude binary MIME types (metadata only).
- Degrade gracefully: if content retrieval fails at interrogation time, fall back to metadata-only context rather than failing the session — but never claim integrity for what was not read.

---

## 2. Lesson: inline (Level 0) round-trips lose evidence

The inline format's context entries are `label` + `url | file` references (`schemas/inline-tez.schema.json`). `file` paths are platform-local; `url`s are frequently private. Our first spec-shaped Level-0 exchange round-tripped to a bundle with **zero context items** — the receiving platform had nothing to interrogate.

What production forced us to build, proposed upstream in [spec#10](https://github.com/tezit-protocol/spec/issues/10):

- Optional embedded content per entry: `content_b64` + declared `hash`/`size`/`mime` (standard base64 alphabet — cannot produce a `---` line, so frontmatter delimiters are safe by construction)
- Import re-hashes decoded content; mismatch is **flagged in item metadata and logged, never silently propagated** — and the item is not silently dropped either (the recipient should see that evidence arrived corrupted)
- Embedding budgets with reference-only fallback for oversized items, and an import-side total document cap

All additive; consumers that ignore the new fields parse the document exactly as today.

---

## 3. Lesson: verification needs preconditions

TIP §5.5 requires automated checks that the cited `item-id` exists and the `location` exists. In the black-hole state, both passed — against metadata — while no bytes existed for any claim to be checked against. A single `"verified": true` boolean cannot express what was actually established.

[spec#11](https://github.com/tezit-protocol/spec/issues/11) proposes splitting the flag (`exists_verified`, `integrity_verified`, with `verified` kept and required to imply both) plus a normative precondition: no `verified` without retrievable, hash-matching bytes. This composes with [#5](https://github.com/tezit-protocol/spec/issues/5)'s semantic levels — it is the rung *below* Level 1. We also recommend a strict mode (downgrade citations with missing/mismatching hashes to unverified, surfaced to the recipient); we default it ON in production environments.

---

## 4. The codeword probe (methodology we now run routinely)

The single most useful test we built. It detects all three lessons' failure modes and costs one context item:

1. **Seed** a nonsense fact into a context item's bytes only — never in synthesis, manifest, or frontmatter. Ours: `The rollback codeword for the deployment is MARMALADE-7.`
2. **Content check:** `GET` the item's content → expect 200 and `sha256(served bytes) ==` declared hash.
3. **Grounding check:** interrogate for the codeword → expect `grounded`, the codeword in the answer, a citation to the item, and citation integrity computed from stored bytes.
4. **Abstention control:** interrogate a bundle without the item → expect TIP-correct abstention (proves step 3 wasn't answered from leakage).
5. **Round-trip check:** inline-export → import into a fresh bundle → repeat steps 2–3 against the *imported* bundle.

Proposed as canary additions to the official test bundles in [spec#9](https://github.com/tezit-protocol/spec/issues/9). A related habit worth adopting in any implementation's CI: probe the advertised API surface against live routes — we shipped a versioned route alias that registered zero routable paths (framework quirk: already-prefixed route objects don't get re-prefixed), so the documented `/api/v1/` family 404'd while the primary mount worked. Advertised-vs-live drift is a conformance question, not just a bug class.

---

## 5. Production constants (first-integration reference points, not normative)

| Concern | Value we shipped |
|---|---|
| Per-item content size cap (storage) | 10 MiB |
| Interrogation excerpt budget | 32 KiB/item, truncation marker, sanitized, text-like MIME only |
| Inline export embedding budget | 64 KiB/item, 128 KiB/document (pre-base64); oversized → reference-only |
| Inline import document cap | 256 KB |
| Context items per tez | 1,000 |
| TIP interrogation rate limits | 100/user, 300/tez, 120/session per hour window |
| MIME handling | allowlist; unknown values downgraded to `text/plain` |

These are the numbers that survived contact with production load and abuse-surface review; future spec guidance (e.g. the TIP Enterprise Addendum's cost ceilings) may want defaults in these ranges.

---

## 6. Security hardening parity

We implemented the upstream security audit log's patterns in a second, architecturally different stack (multi-tenant Postgres/Redis enterprise platform vs the reference relay): Unicode/invisible-character sanitization (P-014/P-049), prompt-injection framing and delimiter isolation (P-001), interrogation session binding to `{tez, user, account}` with rotation on mismatch (P-003), MIME allowlisting (relay finding #15), citation integrity metadata (P-012/P-018), inline import size caps (P-041), item count caps (P-042), per-user/tez/session TIP rate limits (P-022), and audit-trail wiring for session and rate-limit events.

**Confirmation for the audit log's authors: every pattern was implementable without architecture changes.** Known gaps we have not closed, matching the log's "advanced" tier: claim-to-source semantic validation (P-019/P-020 — i.e., [#5](https://github.com/tezit-protocol/spec/issues/5) Level 3), byte-level MIME sniffing (P-039), and extraction-pattern anomaly detection.

---

## 7. MCP surface feedback (pointer)

Agent-facing production use needed the **knowledge core loop** (draft → add context → set synthesis → publish → interrogate → inline export/import) rather than only the transfer plane the reference server currently exposes. The highest-leverage pattern: agents publish work products as tezits and consumers `interrogate` instead of trusting serialized dicts — with abstention as the protocol-correct outcome when evidence doesn't cover the question. Details, including the trust-model lessons (tenant scoping from verified auth context, id validation before URL construction, typed error lanes agents can act on): [mcp-server#24](https://github.com/tezit-protocol/mcp-server/issues/24).

---

## What worked well (so the lessons above land with context)

- **Abstention-honest classification** — made every defect above observable; the protocol's best practical property.
- **Profiles** — the knowledge/coordination/code-review split mapped cleanly onto real workflows; authoring two companion profiles required no core-spec changes.
- **The inline format** — extending it (embedded content) was trivially backward compatible; good bones.
- **The security audit log** — directly actionable; we treated it as a checklist and it held up (§6).

*— Ragu Platform Team*
