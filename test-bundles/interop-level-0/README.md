# Level 0 Interoperability Test Bundle

**Bundle ID**: `interop-level-0-2026-02`
**Tezit Protocol Version**: 1.2.5
**Contributed By**: Ragu Platform
**Last Updated**: June 11, 2026

---

## Purpose

This test bundle provides reference Level 0 (Inline Tez) examples for verifying that an
implementation can correctly parse, display, and interrogate inline tezits across all
standard profiles. Level 0 is the simplest conformance level: a single Markdown file with
YAML frontmatter containing all metadata and synthesis.

The bundle tests:

1. **Knowledge profile parsing** -- Can the system parse an inline tez with standard
   knowledge profile metadata and citations?
2. **Coordination profile parsing** -- Can the system parse an inline tez with the
   coordination surface schema, including assignees, recipients, and status?
3. **Code review profile parsing** -- Can the system parse an inline tez with the
   code review surface schema, including findings, severity summaries, observation
   types, and confidence metadata (v0.2.0)?
4. **Cross-platform portability** -- Can a tez created on one platform be loaded on
   another without modification?
5. **Embedded content round-trip** -- Can implementations with embedded-content
   support decode, hash-check, and interrogate content carried inline?

---

## Bundle Contents

```
interop-level-0/
├── README.md                    # This file
├── knowledge-profile.md         # Inline tez: revenue analysis (knowledge profile)
├── embedded-content-canary.md    # Inline tez: embedded content canary (knowledge profile)
├── coordination-profile.md      # Inline tez: sprint task (coordination profile)
├── code-review-profile.md       # Inline tez: auth token review (code_review profile)
└── test-queries.json            # Validation queries for each profile
```

---

## How to Run Interoperability Tests

### Step 1: Load Each Inline Tez

For each `.md` file, parse the YAML frontmatter and Markdown body. Verify that:

1. The `tezit_version` field is present and equals `"1.2"`.
2. The `profile` field is present and matches one of: `knowledge`, `coordination`,
   `code_review`.
3. Profile-specific surface fields (if present) validate against the corresponding
   JSON Schema.
4. Citations in the Markdown body use the `[[item-id]]` or `[[item-id:location]]`
   format.

### Step 2: Execute Test Queries

Submit the queries from `test-queries.json` against the loaded tez. Each query
specifies which inline tez file it targets and the expected behavior.

Queries marked with `capability_gated: true` and `required_capability:
"embedded_context_content"` are required only for implementations that support
embedded content; implementations without embedded-content support must not start
failing Level 0.

The embedded-content canary keeps the canary fact only in decoded context bytes:
plain grep for the codeword across `test-bundles/interop-level-0/` should hit
only `test-queries.json`; decoding the canary `content_b64` with `base64 -d`
and grepping the decoded bytes should hit the canary sentence.

### Step 3: Validate Results

Compare responses against the passing criteria in each query object.

---

## Profile Coverage

| Profile | File | Surface Schema | Key Features Tested |
|---------|------|---------------|---------------------|
| `knowledge` | `knowledge-profile.md` | None (standard) | Citations, factual grounding, methodology |
| `knowledge` | `embedded-content-canary.md` | None (standard) | Optional embedded context content, hash verification, capability-gated interrogation |
| `coordination` | `coordination-profile.md` | `coordination-surface.schema.json` | Status, assignee, recipients, due date, checklist |
| `code_review` | `code-review-profile.md` | `code-review-surface.schema.json` | Findings, severity, observation_type, confidence (v0.2.0), observation_summary |

---

## Interoperability Requirements

For a platform to claim Level 0 interoperability:

1. All required inline tez files MUST parse without error.
2. YAML frontmatter MUST be correctly separated from Markdown body.
3. Profile-specific metadata MUST be accessible for display or filtering.
4. Citations MUST be recognized (though resolution is not required at Level 0).
5. Unknown fields in the frontmatter MUST be preserved (not silently dropped).
6. Embedded-content queries are capability-gated and required only for
   implementations that support embedded content; implementations without
   embedded-content support must not start failing Level 0.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-06-11 | Added embedded-content canary document and capability-gated queries for implementations that support Inline Tez embedded context content |
| 1.0 | 2026-02-05 | Initial release with knowledge, coordination, and code_review profiles |

---

*This test bundle is contributed by Ragu Platform as part of the Tezit Protocol
interoperability testing initiative. For the full protocol specification, see
[tezit.com/spec/v1.2](https://tezit.com/spec/v1.2).*
