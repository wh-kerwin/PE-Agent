# Platform Discovery Checklist

Use this checklist with the platform, IAM, security, data-owner, and PE representatives before implementing `CustomerPlatformAdapter`. Record only synthetic or approved redacted examples in this repository.

## Case and identity contract

- [ ] Confirm Case endpoint, method, version, ownership, SLA, and change-notification channel.
- [ ] Confirm authoritative `caseId`, immutable `caseVersion`, supported `YIELD_DROP` discriminator, and stale-version behavior.
- [ ] Confirm SSO/IAM delegation flow; identity and tenant must come from a verified session, never request data.
- [ ] Document authorization checks for Case, Lot, Wafer, Tool, Recipe, SPC, FDC, raw links, SSE reconnect, review, and Case Book.
- [ ] Confirm CSRF controls for same-origin cookie mode or controlled bearer-token handling; tokens never appear in URLs.
- [ ] Obtain a least-privilege permission matrix and revocation behavior.

## Read-only manufacturing sources

For Case, Lot/Wafer, Tool events, Recipe, SPC, FDC, and historical Case sources:

- [ ] Name the owner, endpoint, schema/version, authentication scope, timeout, rate limit, and maintenance window.
- [ ] Confirm stable record IDs, pagination, maximum time range, row/point limits, sorting, and version/snapshot semantics.
- [ ] Confirm timestamp timezone and precision; confirm units, allowed conversions, missing-value semantics, and quality flags.
- [ ] Define not-found, partial, stale, permission-denied, timeout, and retryable-unavailable mappings.
- [ ] Confirm source deep-link construction uses a fixed allowlisted route and re-authorizes on navigation.
- [ ] Confirm all V1 manufacturing operations are `READ`; do not register arbitrary URL, SQL, file, or write operations.

## Case Book archive (separate write boundary)

- [ ] Confirm `casebook.write` authorization, required reviewed states, payload schema, idempotency, retry semantics, and external archive ID.
- [ ] Confirm archive cannot trigger MES or production control actions.
- [ ] Keep archive disabled through discovery, shadow, and smoke testing; enabling it requires an explicit production change approval.

## Network, data, and operations

- [ ] Confirm platform, database, and model egress destinations by DNS/IP, port, TLS trust, proxy, and deployment region.
- [ ] Confirm field classification, minimization/redaction, retention/deletion, data residency, and approved model egress.
- [ ] Confirm database endpoint and secret delivery; Helm deploys no in-cluster PostgreSQL and stores no secret values.
- [ ] Confirm audit fields, metrics, trace propagation, log redaction, alert owners, and incident escalation.
- [ ] Confirm SSE ingress has buffering disabled and suitable idle/read timeouts.
- [ ] Confirm rollback, migration ownership, backup/restore evidence, RTO/RPO, and maintenance communications.

## Evidence required to leave discovery

- [ ] Approved field mapping based on `field-mapping-template.md`.
- [ ] Synthetic or approved redacted request/response/error examples for every source.
- [ ] IAM permission matrix and negative cross-tenant test cases.
- [ ] Data-flow/privacy/security approval and approved network allowlist.
- [ ] Adapter contract tests cover version conflict, authorization, partial data, timeout, units, timezone, and fixture-free imports.
- [ ] Named PE and platform owners approve shadow entry; unchecked external items remain blockers, not mock-complete work.
