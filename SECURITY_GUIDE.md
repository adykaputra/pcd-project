# Security Incident Response Guide

This document provides a concise checklist for responding to security incidents related to this project (tampering, unauthorized access, suspected data leakage, etc.). Keep this guide in the repo so responders can act quickly.

## Incident Response Checklist (Quick)

1. **Triage (Immediate, 0-15 min)** 🚨
   - Confirm the alert source (GitHub workflow, Slack, monitoring) and capture run id / timestamp.
   - Obtain the tampered artifact (`tampered-ids` artifact from CI) and note affected IDs.
   - Mark the incident as `IN_PROGRESS` in your tracking system (GitHub Issue or PagerDuty ticket).

2. **Containment (15-60 min)** 🔒
   - If tampering detected: take a snapshot/backup of the audit DB (`data/audit_log.db`) and move to a secure analysis location.
   - Rotate critical keys if you suspect key compromise (e.g., `AUDIT_HMAC_KEY`, `JWT_SECRET`). Use your KMS to generate new values and update secrets.
   - Isolate related services if ongoing suspicious activity is detected (block connections, remove elevated credentials).

3. **Investigate (1-24 hours)** 🔍
   - Pull recent logs (structured JSON logs) and filter by `request_id`, `event_type`, and `user_role`.
   - Cross-check tampered row signatures with expected HMACs and capture the discrepancy report.
   - Determine scope and timeline: affected records, ingress vectors, and whether PII was impacted.

4. **Remediation (24-72 hours)** 🛠️
   - If integrity breach is confirmed, restore audit DB from the last known-good backup and export signed records for forensic storage.
   - Reissue credentials and rotate secrets (JWT secret, HMAC key, OpenAI keys if relevant).
   - Harden access policies and remove any compromised tokens or credentials.

5. **Recovery & Validation** ✅
   - Re-run integrity checks until `integrity_ok` returns true.
   - Re-enable normal operation and monitor closely for any recurrence.

6. **Postmortem & Lessons Learned (Within 7 days)** 📄
   - Publish a blameless postmortem including timeline, root cause, mitigation, and action items.
   - Add automated tests or CI checks to prevent similar issues and track completion of follow-up TODOs.

---

## Forensic Data to Collect
- GitHub workflow run id and logs
- Tampered artifact (`tampered-ids.json`) from the workflow
- Copies of the affected `data/audit_log.db`
- Relevant structured logs (JSON) covering the incident timeframe
- Any related OS / container logs, and access control logs

## Communications & Escalation
- Assign a lead and establish an internal channel (Slack #incidents).
- Notify stakeholders and legal if PII or high-sensitivity data is involved.

## Notes on Long-term Hardening
- Use a KMS for HMAC signing (avoid storing `AUDIT_HMAC_KEY` as plain env var).
- Consider exporting HMACs to an external append-only store and anchoring to an external transparency log.
- Use a managed DB for high-availability audit storage and immutable storage options.

---

*Keep this document updated as process improvements or tools are added.*
