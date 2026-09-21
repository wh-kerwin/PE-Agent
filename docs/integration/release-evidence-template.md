# Release Evidence

Complete this record for each candidate promoted beyond `mock-recorded`.

## Build identity

- Git SHA:
- Build time (UTC):
- Deployment profile:
- API image digest:
- Worker image digest:
- Frontend image digest:

## Versioned contracts

- Report schema version and SHA-256:
- Workflow ID/version and SHA-256:
- Jev question-set version and SHA-256:
- Tool-registry version and SHA-256:
- Requested and resolved test model:

## Gate results

- Repository contract validation:
- Backend Ruff/mypy/unit/integration:
- Frontend typecheck/unit/build:
- Desktop/mobile E2E and accessibility:
- Compose validation:
- Helm lint/template validation:
- Dependency scan:
- Secret scan:

## Promotion controls

- Platform profile is explicit and does not fall back to mocks:
- Production-readiness checklist approved:
- Golden Case comparison attached:
- Rollback configuration saved and tested:
- Named platform, IAM, data, TypeSafe, Kubernetes/DB, and PE owners recorded:

Do not attach credentials, environment dumps, customer payloads, manufacturing evidence, or model request bodies. Mock evidence must be marked synthetic and cannot satisfy production readiness.
