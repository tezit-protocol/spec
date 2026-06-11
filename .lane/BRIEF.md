# Lane S11 — TIP citation existence/integrity preconditions (implements tezit-protocol/spec#11)

## Hard rules

1. This implements the MAINTAINER-ACCEPTED proposal in issue #11 (read it first: https://github.com/tezit-protocol/spec/issues/11). Implement what the issue proposes — do not redesign. Additive/backward-compatible is the bar: `verified` stays, two new booleans join it.
2. Protected: do not touch `TEZIT_PROTOCOL_SPEC_v1.2.md`, `schemas/inline-tez.schema.json`, `test-bundles/interop-level-0/` (a parallel lane owns those). Do not touch `test-bundles/tip-compliance/` content semantics (its README already documents the content-endpoint hash check from #14 — you may cross-reference it, not rewrite it).
3. `git add` ONLY: `TEZ_INTERROGATION_PROTOCOL.md`, `schemas/tip-response.schema.json`, `schemas/README.md` (if it documents response fields), `.lane/`.
4. Commit per coherent unit (spec text, schema). Do NOT push.
5. Public repo: no internal platform/business references beyond what issue #11 states.

## Read these FIRST

- Issue #11 (full proposal: normative precondition + flag split + strict mode; its relation to issue #5's semantic levels).
- `TEZ_INTERROGATION_PROTOCOL.md` §5.5 (citation verification requirements) and §6.5 (response metadata) — and the document's own version/changelog conventions.
- `schemas/tip-response.schema.json` — current citation object shape.
- Issue #5 (open proposal for semantic verification levels) — your text must explicitly compose with it: existence/integrity are the rungs BELOW its Level 1+; do not implement #5 itself.
- `launch-partners/ragu/PRODUCTION_LEARNINGS.md` §3 (merged production motivation).

## Step 0 (fail fast)

`jq -e . schemas/tip-response.schema.json` must pass and §5.5/§6.5 must exist as described. If repo state contradicts this brief, STOP: `.lane/report.json` `{"blocked": "<found>"}` + `.lane/DONE`.

## Deliverables

1. **Spec text (§5.5)**: add the normative precondition — a citation MUST NOT be marked `verified` unless (a) the cited item's content is retrievable and (b) the content used for verification hash-matches the item's declared content hash; verification MUST be anchored to bytes actually served/stored, not metadata assertions. Keep the existing checks (1)(2) and frame them as `exists_verified`.
2. **Spec text (§6.5)**: citation metadata gains `exists_verified` and `integrity_verified` (booleans, OPTIONAL for backward compatibility); `verified` is retained and MUST imply both when emitted as true. Include the issue's example JSON. Add a non-normative "strict mode" note: implementations SHOULD support downgrading citations with missing/mismatching content to unverified, surfaced to the recipient; strict mode recommended ON in production.
3. **Schema**: `schemas/tip-response.schema.json` — add the two optional booleans to the citation object with descriptions carrying the implication rule. No required-field changes.
4. **Composition note**: one short paragraph (in §5.5 or wherever verification levels are discussed) placing existence → integrity → semantic (#5 Levels) as the ladder, citing issue #5 as the open proposal above this floor.
5. **Versioning**: follow the TIP document's own convention for a backward-compatible addition (current TIP v1.0.3); record the choice in the report under `versioning_decision`, with the changelog/version-history entry added.
6. **Report**: `.lane/report.json` — `{"files_changed": [], "versioning_decision": "", "findings": [], "deliberately_not_done": []}` + empty `.lane/DONE`.

## Validation gates (orchestrator re-runs unmasked)

```
jq -e . schemas/tip-response.schema.json
jq -e '(.blocked|not)' .lane/report.json
test -f .lane/DONE
grep -n "integrity_verified" TEZ_INTERROGATION_PROTOCOL.md schemas/tip-response.schema.json   # both must hit
```
