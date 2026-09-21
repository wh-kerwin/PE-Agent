# Production Readiness Checklist

All evidence must reference an approved ticket, test run, dashboard, or owner. A checked box based only on mock data is insufficient for platform-dependent items.

## Contract and product gates

- [ ] Platform discovery checklist and every field mapping are approved by source owners.
- [ ] Real Case/version behavior, supported Yield Drop discriminator, units, timezone, and partial/missing semantics are verified.
- [ ] Platform adapter no longer raises `ADAPTER_NOT_CONFIGURED`; contract tests use approved synthetic/redacted samples and import no mock fixtures.
- [ ] API/SSE/error contracts and report schema/link validators pass.
- [ ] Case Book review, permission, idempotency, failure, and retry behavior are approved before archive is enabled.

## Security and privacy

- [ ] Host SSO/IAM identity is authoritative; body/query cannot assert user, tenant, or role.
- [ ] Cross-tenant, guessed task ID, SSE reconnect, raw-reference, related entity, review, and archive negative tests pass.
- [ ] Manufacturing tools remain read-only and allowlisted; no arbitrary URL, SQL, path, or production-action capability exists.
- [ ] Prompt injection tests cannot change authorization, tool registry, data scope, or output contract.
- [ ] Secrets are runtime-injected, rotated, absent from images/manifests/logs, and scoped least privilege.
- [ ] Data classification, minimization, approved model egress/region, retention, deletion, and audit requirements are signed off.
- [ ] TLS, ingress, CSRF/cookie or bearer handling, NetworkPolicy, egress allowlist, and dependency certificates are validated in the target environment.

## Reliability and deployment

- [ ] Immutable image is scanned/SBOM-attested and runs non-root with read-only root filesystem and dropped capabilities.
- [ ] External PostgreSQL capacity, HA, backup/restore test, retention, RTO/RPO, connection limits, and TLS are approved.
- [ ] Migration Job succeeds on a production-like copy; forward/rollback compatibility and ownership are documented.
- [ ] API and worker scale independently; probes, requests/limits, disruption budget, queue lease/fencing, and graceful shutdown are tested.
- [ ] SSE buffering is disabled at every proxy; heartbeat, idle timeout, cursor expiry, reconnect, and authorization revocation are tested.
- [ ] Dependency timeout/rate-limit/5xx, partial result, restart, duplicate request, cancellation race, and stale worker tests pass.
- [ ] `python scripts/validate_deploy.py` and production preflight pass without placeholder allowance.

## Quality and operations

- [ ] Unit, integration, contract, static, schema/reference, and approved smoke suites pass with retained evidence.
- [ ] Historical evaluation meets agreed evidence-grounding and safety thresholds; CJK and no-evidence behavior are reviewed by PE.
- [ ] Shadow period and sample size meet the approved plan; discrepancies and unresolved risks have owners.
- [ ] Dashboards cover latency, completion/partial/timeout, invalid output, reconnect recovery, model/source errors, queue depth, and database health.
- [ ] Logs/traces contain approved identifiers/hashes only, no keys, full production payloads, downstream error bodies, or internal reasoning.
- [ ] Alerts, on-call, incident response, credential revocation, rollback, maintenance, support, and customer communication paths are rehearsed.

## Release authorization

- [ ] PE owner signs investigation quality and user workflow.
- [ ] Platform/data owners sign source contracts and capacity.
- [ ] Security/privacy owners sign IAM, network, data handling, and model egress.
- [ ] Operations owner signs deployment, monitoring, backup/restore, rollback, and runbook.
- [ ] Product/release owner approves pilot scope and explicit `platform-production` configuration.
- [ ] Archive remains `false` unless a distinct Case Book enablement approval is attached.

Release date, approvers, image digest, chart version, migration revision, configuration revision, and rollback target: `<approved release record>`.
