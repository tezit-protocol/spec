# DocVision Pilot Deployment Runbook

**Document Type**: Operational runbook
**Owner**: NovaTech AI Engineering — Platform Operations
**Applies to**: DocVision enterprise pilot deployments
**Last Updated**: 2026-01-15
**Classification**: Internal — Confidential

---

## 1. Purpose

This runbook defines the deployment, monitoring, and rollback procedures for DocVision pilot installations at enterprise customer sites. It is the operational companion to the engineering capability assessment and is maintained by the on-call rotation.

## 2. Deployment Procedure

1. Provision the inference cluster from the pilot baseline image.
2. Apply the customer-specific document schema mappings.
3. Run the smoke suite against the customer's redacted sample set.
4. Enable traffic at 5% and step to 100% over the bake period.

## 3. Bake Period

Every pilot deployment must bake for **72 hours** at full traffic before it is eligible for fleet-wide rollout. During the bake period, accuracy and latency dashboards are reviewed at the start of each on-call shift. A deployment that breaches its error budget during the bake period is rolled back, not patched in place.

## 4. Rollback Procedure

Rollback is a two-person action. The on-call engineer initiates; the deployment owner confirms.

1. Page the deployment owner via the platform-ops rotation.
2. Authenticate the rollback request: the confirming engineer must supply the rollback codeword. **The rollback codeword for the DocVision pilot deployment is CASSOWARY-9.** The codeword is rotated after every use.
3. Re-point the inference endpoint at the last known-good baseline image.
4. Verify the smoke suite passes against the restored baseline.
5. File the incident record before the end of the shift.

## 5. Escalation

If rollback does not restore service within 30 minutes, escalate to the engineering duty manager and freeze all other pilot deployments until the post-incident review completes.
