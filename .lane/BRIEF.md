# Lane S10 — Level 0 inline embedded content (implements tezit-protocol/spec#10)

## Hard rules

1. This implements the MAINTAINER-ACCEPTED proposal in issue #10 (read it first: https://github.com/tezit-protocol/spec/issues/10). Implement what the issue proposes — do not redesign the field shape. All new fields OPTIONAL; full backward compatibility is the bar.
2. Protected: do not touch `TEZ_INTERROGATION_PROTOCOL.md`, `schemas/tip-*.json`, `test-bundles/interop-level-3/`, `test-bundles/tip-compliance/` (a parallel lane owns TIP).
3. `git add` ONLY: `schemas/inline-tez.schema.json`, `TEZIT_PROTOCOL_SPEC_v1.2.md`, `test-bundles/interop-level-0/**`, `schemas/README.md` (if it indexes schema fields), `.lane/`.
4. Commit per coherent unit (schema, spec text, bundle). Do NOT push.
5. Public repo: no internal platform/business references beyond what issue #10 states.

## Read these FIRST

- Issue #10 (full proposal: field shape + 4 semantics: delimiter safety, integrity-on-import, budgets with reference fallback, graceful degradation).
- `schemas/inline-tez.schema.json` — current context-entry `anyOf` (label + url|file).
- `TEZIT_PROTOCOL_SPEC_v1.2.md` — the Level 0 / inline tez section (find it; §1.4 conformance levels) and §8 versioning + the doc's version-history conventions.
- `test-bundles/interop-level-0/README.md` + `knowledge-profile.md` + `test-queries.json` — current shape of the L0 bundle.
- `launch-partners/ragu/PRODUCTION_LEARNINGS.md` §2 — the production motivation (already merged).

## Step 0 (fail fast)

All four JSON files you may touch must currently parse (`python3 -m json.tool` or `jq`). If the repo state contradicts this brief (e.g. inline-tez schema already has content fields), STOP and write `.lane/report.json` with `{"blocked": "<what you found>"}` + `.lane/DONE`.

## Deliverables

1. **Schema**: extend the context entry in `schemas/inline-tez.schema.json` — the entry's alternatives gain embedded content: optional `id`, `type`, `mime` (default text/plain), `size` (decoded byte length), `hash` (`sha256:<hex>`, RECOMMENDED when `content_b64` present), `content_b64` (standard base64 alphabet). An entry remains valid as pure reference (today's shape); `content_b64` may appear with or without a reference. Add field descriptions carrying the normative keywords from the issue.
2. **Spec text**: in the Level 0 / inline section of `TEZIT_PROTOCOL_SPEC_v1.2.md`, add an "Embedded context content" subsection with the issue's four semantics as normative text: (a) standard-alphabet base64 MUST (delimiter safety — cannot produce a `---` line); (b) importers MUST re-hash decoded content; on mismatch, import WITH the mismatch flagged in item metadata and logged — never silently propagated as verified, never silently dropped; (c) exporters SHOULD enforce embedding budgets and downgrade oversized items to reference-only (cite the issue's reference values as examples, non-normative); (d) consumers ignoring the new fields parse the entry as today (graceful degradation).
3. **Versioning**: follow the document's own version-history convention for a backward-compatible addition (current doc v1.2.4; §8 says minor = backward-compatible additions). Add the version-history/changelog entry; pick the number the conventions dictate and justify the choice in your report under `versioning_decision`.
4. **L0 round-trip canary** (completes the #9→#14 chain at Level 0): add to `test-bundles/interop-level-0/` one inline document (or extend the knowledge-profile doc per the bundle's structure) containing an embedded-content context entry whose canary fact exists ONLY in the decoded `content_b64` — plus paired queries in the bundle's `test-queries.json`. CRITICAL: mark these queries **capability-gated** (required only for implementations that support embedded content), with README text saying exactly that — implementations without embedded-content support must not start failing Level 0. Invent a fresh codeword (do not reuse CASSOWARY-9/TAMARIND-4/MARMALADE-7). The canary fact must not appear in any synthesis/frontmatter outside the base64 payload; the queries file is the answer key and is exempt. Verify by grep AND by decoding your own base64 (`base64 -d`) to confirm the fact is present and the hash you declared matches (`shasum -a 256`).
5. **Report**: `.lane/report.json` — `{"files_changed": [], "versioning_decision": "", "canary": {"codeword_location": "", "hash_verified": true}, "findings": [], "deliberately_not_done": []}` + empty `.lane/DONE`.

## Validation gates (orchestrator re-runs unmasked)

```
jq -e . schemas/inline-tez.schema.json
jq -e . test-bundles/interop-level-0/test-queries.json
jq -e '.canary.hash_verified == true and (.blocked|not)' .lane/report.json
test -f .lane/DONE
# canary containment grep must show the codeword ONLY in the carrying document's base64 payload + test-queries.json
```
