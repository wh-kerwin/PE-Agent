# FDE Runbook

This runbook separates local contract proof, customer discovery, shadow operation, and production release. It never authorizes production writes by itself.

## Profiles

| Profile | Platform data | Decision adapter | Archive | Intended use |
|---|---|---|---|---|
| `mock-recorded` | synthetic fixture | recorded | off | default local/static verification; no external service |
| `mock-live-jev` | synthetic fixture | live approved model endpoint | off | model integration verification |
| `platform-shadow` | customer platform, read-only | live approved model endpoint | off | non-user-visible comparison and evidence collection |
| `platform-production` | customer platform, read-only | live approved model endpoint | off by default | controlled user pilot; archive separately enabled after approval |

Checked-in `.invalid.example` origins and synthetic passwords are non-routable placeholders. Supply all real origins and secrets through the customer's secret/configuration system; never edit them into manifests.

## Preflight and static checks

From repository root:

```sh
python scripts/validate_deploy.py
python scripts/preflight.py --profile mock-recorded
```

`mock-recorded` must pass without DNS, database, platform, model, Docker, or Kubernetes access. For checked-in platform templates only, syntax can be checked with `--allow-synthetic-placeholders`; that flag is not production readiness evidence.

For a real shadow/production preflight, override placeholder origins and inject credentials into the process environment, then run without the placeholder flag. Preflight validates configuration only and deliberately does not contact dependencies or print secret values.

## Local Compose

Use the base file plus exactly one explicit override. Supply the matching profile file explicitly; Compose does not load `deploy/profiles/*.env` automatically. Export runtime-only secrets (for example `PE_AGENT_TYPESAFE_API_KEY`) through the approved secret mechanism before starting a live profile.

```sh
docker compose --env-file deploy/profiles/mock-recorded.env -f deploy/compose.yaml -f deploy/compose.mock-recorded.yaml up --build
```

Equivalent overrides exist for `mock-live-jev`, `platform-shadow`, and `platform-production`. Compose PostgreSQL is local-development-only. Confirm migrations complete before API and worker start. Do not treat a mock profile as proof of a customer integration.

## Kubernetes/Helm

The chart requires an externally operated PostgreSQL URL in an existing Secret (`externalDatabase.secretName` / `urlKey`) and optional runtime credentials in the customer secret system. The chart contains no Secret values and no PostgreSQL workload.

```sh
helm lint deploy/helm/pe-agent
helm template pe-agent deploy/helm/pe-agent --values deploy/helm/pe-agent/values-platform-shadow.yaml
```

Before install, replace placeholder origins, configure ingress/TLS and approved egress CIDRs, verify NetworkPolicy selectors against the actual database location, and verify the ingress controller honors disabled SSE buffering. The pre-install/pre-upgrade migration Job must succeed before roll-out.

## Non-destructive smoke

```sh
python scripts/smoke_test.py --base-url https://pe-agent.invalid.example
```

The default performs only liveness. `--analysis` creates one idempotent synthetic/read-only analysis and is allowed only in a designated test tenant with an approved synthetic Case. The script has no archive option and never invokes Case Book. Do not use real Case identifiers in command history.

## Shadow sequence

1. Confirm platform discovery checklist, field mapping, IAM negative tests, and security/data approvals.
2. Deploy `platform-shadow` with archive off and no user entry point.
3. Verify authorization on every read, source/version/units/timezone, partial-data behavior, and audit redaction.
4. Run approved synthetic cases, then approved historical offline cases; compare with PE labels.
5. Exercise dependency timeout/429/5xx, revocation, restart, migration rollback, SSE reconnect, and NetworkPolicy denial.
6. Review metrics and traces without sensitive payloads. Obtain named PE, platform, security, and operations sign-off.

## Production and rollback

- Deploy immutable image digest after checklist approval; canary API and worker independently.
- Keep Case Book archive off until review permissions, idempotency, and rollback are separately approved.
- Pause entry points and scale worker to zero to stop new processing; preserve task truth and audit records.
- Roll application back only to a schema-compatible image. Database migrations require the approved forward/restore plan; do not improvise destructive downgrades.
- On authorization leakage, unexpected write, secret exposure, or cross-tenant result: disable ingress/worker, revoke credentials, preserve audit evidence, and follow the customer incident process.
