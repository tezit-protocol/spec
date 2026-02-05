# Vendor Extensions

Vendor extensions use reverse-domain naming to avoid conflicts with standard extensions and other vendors. Any organization implementing the Tezit Protocol can register a vendor namespace by opening a PR to this directory.

Vendor extensions are maintained by their respective organizations. This registry provides discoverability and prevents namespace collisions.

## Registered Namespaces

### `com.ragu.*` -- Ragu Platform

**Organization:** Ragu Platform
**Type:** Enterprise AI orchestration
**Website:** [ragu.ai](https://ragu.ai)

Ragu is an enterprise AI orchestration platform with 11 microservices, an agentic RAG pipeline, fine-grained authorization via OpenFGA, and multi-model support. Ragu's vendor extensions address enterprise-specific needs around access control, evaluation, retrieval transparency, and multi-tenancy.

| Extension | Description | Status |
|-----------|-------------|--------|
| `com.ragu.fga-access` | Fine-grained access control within tezits. Integrates with OpenFGA to enforce per-context-item and per-section authorization, enabling tezits where different recipients see different subsets of content. | Active |
| `com.ragu.eval-metrics` | Interrogation quality metrics. Captures groundedness, relevance, and faithfulness scores for interrogation sessions. Being proposed for standardization as `tezit-eval`. | Active (standardizing) |
| `com.ragu.retrieval-transparency` | Retrieval method and scoring data. Records which retrieval strategy was used (semantic search, keyword, hybrid, agentic), the similarity scores, and the ranking methodology -- making the RAG pipeline auditable. | Active |
| `com.ragu.multi-tenant` | Tenant isolation metadata. Embeds tenant identifiers and isolation boundaries within tezits, ensuring that multi-tenant platforms can share tezits across organizational boundaries without leaking data between tenants. | Active |

---

### `chat.mypa.*` -- MyPA.chat

**Organization:** MyPA.chat
**Type:** Team coordination platform
**Website:** [mypa.chat](https://mypa.chat)

MyPA.chat is a personal AI assistant and team coordination platform. As the first implementer of the Tezit Protocol, MyPA.chat focuses on consumer-facing Tez creation, interrogation, and team-based knowledge sharing.

| Extension | Description | Status |
|-----------|-------------|--------|
| *(No extensions registered yet)* | MyPA.chat currently uses standard extensions only. Vendor extensions will be registered here as the platform develops team-specific capabilities. | -- |

---

## Registering a Namespace

To register a vendor namespace:

1. Open a PR adding your organization to this file
2. Use reverse-domain naming (e.g., `com.yourcompany.*`, `io.yourservice.*`)
3. Include: organization name, type, website, and initial extension list (if any)
4. One approval from a maintainer is sufficient for namespace registration

Namespace registration does not require a full extension proposal. It simply reserves the prefix to prevent conflicts.
