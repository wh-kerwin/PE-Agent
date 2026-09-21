# Known Limitations

The mock-first vertical slice proves the application contracts and deployment shape, not customer production readiness.

## G5 dependencies not validated

- **Platform API:** no official customer API, sanitized payload set, rate limit, pagination, or source SLA has been integrated.
- **IAM:** development identity is server-generated; customer SSO, tenant isolation, role mapping, CSRF, and permission revocation have not been validated.
- **Manufacturing data:** yield, equipment, recipe, SPC, FDC, and historical Case evidence are deterministic fixtures. Field semantics, units, timezone behavior, and data quality have not been validated against a fab source.
- **Case Book:** the adapter returns synthetic archive identifiers. Customer write permission, idempotency, retention, and error recovery have not been validated.
- **TypeSafe Jev:** recorded fixtures exercise the decision contract. A live smoke is opt-in; no production workload, data-egress approval, CJK evaluation, latency/load envelope, or outage rate has been accepted.
- **Operations:** Compose is for demonstration. Production backup/restore, retention, zero-data-retention decision, disaster recovery, load/SSE recovery, audit sampling, image scanning, and rollback require environment-owner evidence.

## Promotion rule

Do not enable `platform-production` from mock results. Complete the platform discovery and field mapping, implement only the customer adapter, pass the shared adapter contracts and sanitized endpoint-response tests, deploy `platform-shadow` with archive disabled, and compare an agreed golden Case set with PE engineers.

Promotion additionally requires named owners and signed evidence for platform API, IAM, manufacturing data, TypeSafe/data egress, Kubernetes/PostgreSQL, and PE acceptance. Track these requirements in the production-readiness checklist and release-evidence record.
