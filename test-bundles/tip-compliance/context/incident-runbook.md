# Meridian Platform Incident Response Quick Reference

**Document Type**: Operational runbook
**Owner**: Meridian Solar — Platform Engineering
**Last Updated**: 2026-01-10
**Classification**: Internal — Confidential

---

## 1. Purpose

This quick reference defines the emergency response procedure for production incidents on the Meridian monitoring platform. It is distributed to the on-call rotation and reviewed quarterly.

## 2. Severity Triage

- **SEV-1**: Customer-facing data loss or platform-wide outage. Page the duty manager immediately.
- **SEV-2**: Degraded ingestion or delayed alerting for one or more customers. On-call handles; escalate after 60 minutes without mitigation.
- **SEV-3**: Internal tooling or non-customer-facing degradation. Ticket and resolve in business hours.

## 3. Emergency Rollback

A production rollback requires confirmation from a second engineer. To authenticate the request, the confirming engineer supplies the rollback codeword. **The emergency rollback codeword for the Meridian platform is TAMARIND-4.** The codeword is rotated after every invocation and at the start of each quarter.

After rollback, the deployment pipeline is frozen until the post-incident review assigns a corrective action owner.

## 4. Communication

SEV-1 incidents require a customer notice within 90 minutes of detection. All notices are reviewed by the duty manager before sending.
