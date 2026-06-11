# Interop Test Bundle: Level 3 - Platform Tez (Market Analysis)

## Overview

This is a **Level 3 (Platform Tez)** interop test bundle for the Tezit Protocol v1.2. It exercises the full feature set of the protocol including synthesis documents, multi-item context, permissions, extensions, and cross-reference citations.

The scenario is a **market entry analysis** for NovaTech AI, a fictional Series A startup evaluating entry into the enterprise document processing market. The bundle contains a synthesis document that references four context items via Tezit citation syntax, plus a fifth context item (an operational runbook) that is deliberately never cited by the synthesis — it carries the content-only canary facts (see below).

## Bundle Structure

```
interop-level-3/
├── README.md                          # This file
├── manifest.json                      # Tezit v1.2 manifest (full Level 3)
├── tez.md                             # Synthesis document
├── context/
│   ├── market-landscape.md            # Market research report
│   ├── technical-assessment.md        # Technical capability assessment
│   ├── financial-projections.md       # 3-year financial model
│   ├── founder-memo.md               # CEO strategic memo
│   └── ops-runbook.md                # Deployment runbook (content-only canary)
├── extensions/
│   └── facts.json                     # tezit-facts extension data
└── test-queries.json                  # 10 test queries with expected behaviors
```

## Tezit Level 3 Features Exercised

| Feature | Status | Details |
|---------|--------|---------|
| Manifest schema | Yes | Full `$schema` reference to v1.2 |
| Synthesis document | Yes | `tez.md` with structured analysis |
| Context items | Yes | 5 items (4 documents, 1 data) |
| Citation syntax | Yes | `[[item-id:location]]` references throughout synthesis |
| Permissions block | Yes | CC-BY-NC-4.0 license, interrogate/fork/reshare enabled |
| Extensions | Yes | `tezit-facts` extension with 5 extracted facts |
| Profile | Yes | `knowledge` profile |

## Test Queries

The `test-queries.json` file contains 10 test queries across five categories:

### Grounded (3 queries)
Queries that should be answerable with proper citations to specific context items.

- **grounded-01**: Market size question (expects `$18.7B`, cites `market-landscape`)
- **grounded-02**: Benchmark results (expects `94.7%`, cites `technical-assessment`)
- **grounded-03**: Revenue projections (expects `$8.4M` for Y2, cites `financial-projections`)

### Abstention (2 queries)
Queries that should result in a refusal or explicit "not in context" response.

- **abstention-01**: Patent portfolio (not covered in any context item)
- **abstention-02**: Comparison to Google Document AI (Google not mentioned in context)

### Partial (1 query)
Queries where the context partially covers the topic.

- **partial-01**: Comprehensive risk analysis (some risks covered, others explicitly noted as missing)

### Hallucination Traps (1 query)
Queries designed to catch models that fabricate information.

- **hallucination-trap-01**: References a CTO that does not exist in the context (Diana Park is CEO; no CTO is mentioned anywhere)

### Cross-Reference (1 query)
Queries requiring synthesis across multiple context items.

- **cross-reference-01**: Runway sufficiency for market entry (requires combining financial projections with technical assessment costs)

### Content Canary (2 queries)
Queries answerable **only** from the bytes of a context item — the target facts appear nowhere in `tez.md`, `manifest.json`, or `extensions/facts.json`.

- **content-canary-01**: Rollback codeword (exists only in `context/ops-runbook.md`; expected value in `test-queries.json`)
- **content-canary-02**: Pilot bake period (exists only in `context/ops-runbook.md`; expected value in `test-queries.json`)

These queries exist because every other grounded query in this bundle can also be answered from the synthesis document — the figures checked by `grounded-01..03` appear in `tez.md` itself. An implementation that never stores context item content (indexing only the synthesis) therefore passes the rest of this suite while violating the protocol's core promise. The canaries detect that failure mode: they ground if and only if context content is stored and interrogable.

**Maintenance rules for this bundle:**

1. The canary facts MUST never be quoted in `tez.md`, the manifest, the facts extension, or any other file in the bundle. (`ops-runbook` is intentionally uncited by the synthesis.)
2. Harnesses SHOULD also fetch the canary item's content via the implementation's content endpoint and verify the served bytes hash-match the stored item — catching implementations that interrogate from an ingest-time cache while the durable store is empty.
3. Because this bundle is public, the canary strings may eventually appear in model training data. Harnesses MAY rewrite the canary file with freshly generated codewords (updating the queries to match) for higher-assurance runs; the bundle structure supports substitution without other changes.

## Validation

A conformant Level 3 Tezit consumer should:

1. Parse `manifest.json` and validate against the v1.2 schema
2. Load and index all 5 context items, including their content bytes
3. Parse citation references in `tez.md` and resolve them to context items
4. Respect the `permissions` block (no commercial use)
5. Load the `tezit-facts` extension and make extracted facts available
6. Answer grounded queries with proper citations
7. Abstain from answering queries outside the context scope
8. Detect hallucination traps (no CTO exists in context)
9. Synthesize across context items for cross-reference queries
10. Ground the content-canary queries from stored context bytes (see above)

## Internal Consistency

All data points in the synthesis document (`tez.md`) are traceable to specific context items. The context documents were authored to be mutually consistent:

- Market size figures in `market-landscape.md` match citations in `tez.md`
- Benchmark numbers in `technical-assessment.md` match the synthesis tables
- Financial projections in `financial-projections.md` match revenue/cost figures
- Strategic rationale in `founder-memo.md` aligns with the recommendations

## License

This test bundle is provided under CC-BY-NC-4.0 for interoperability testing purposes.

---
*Tezit Protocol v1.2 | Interop Level 3 | Created 2026-02-05*
