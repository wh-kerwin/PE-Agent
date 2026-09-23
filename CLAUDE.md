# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Repository context

Read [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) first for the current implementation state, non-negotiable security constraints, verified test baseline, blocked work, and the required end-of-task update process. It is the single-file handoff entry for new sessions. The detailed backlog is [docs/07-development/todo.md](docs/07-development/todo.md).

This repository is a mock-first implementation of an AI Case analysis feature embedded in a PE Duty / Engineer Platform Dashboard. Synthetic fixtures and recorded model responses prove contracts and workflow shape; they are not production-readiness evidence. Do not infer customer API fields or enable real integrations without the official inputs described in the handoff and integration documents.

## Common commands

Run commands from the repository root unless noted otherwise. Python tooling targets Python 3.12+; the current project may also be exercised with a compatible newer local interpreter.

### Install development dependencies

```sh
python -m pip install -r scripts/requirements.txt
python -m pip install -e "backend[dev]"
npm ci --prefix frontend
```

The frontend dependency install may be blocked by the execution environment. Do not bypass that restriction; report frontend checks as blocked when `node_modules` is unavailable.

### Backend checks

```sh
python -m pytest -c backend/pyproject.toml backend/tests
python -m pytest -c backend/pyproject.toml backend/tests/unit/test_analysis_api.py
python -m pytest -c backend/pyproject.toml backend/tests/integration/test_task_repository.py
python -m ruff check backend/src backend/tests scripts
python -m mypy --config-file backend/pyproject.toml backend/src
python scripts/validate_contracts.py
```

The integration module uses Testcontainers and PostgreSQL; it skips when Docker is unavailable. The live TypeSafe test is opt-in and must not become ordinary CI coverage.

### Frontend checks

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Use Vitest's file filtering for a focused test, for example:

```sh
npm --prefix frontend exec vitest run src/store/caseAnalysis.test.ts
```

For UI changes, start the dev server and exercise the relevant flow in a browser when dependencies are available:

```sh
npm --prefix frontend run dev
```

### Deployment and static validation

```sh
python scripts/validate_deploy.py
python scripts/preflight.py --profile mock-recorded
python scripts/smoke_test.py --base-url http://localhost:8000 --case-id SYN-CASE-PRESSURE-001 --case-version 1

docker compose --env-file deploy/profiles/mock-recorded.env \
  -f deploy/compose.yaml -f deploy/compose.mock-recorded.yaml config --quiet

docker compose --env-file deploy/profiles/mock-recorded.env \
  -f deploy/compose.yaml -f deploy/compose.mock-recorded.yaml up --build
```

The mock Compose profile is the safe local/demo path. It uses deterministic synthetic platform data and recorded decisions, with archive disabled by default. Production and platform profiles must fail closed when their external adapters are not configured.

## Architecture

### Backend request path

`backend/src/pe_agent/main.py` constructs the FastAPI app, SQLAlchemy async engine/session factory, settings, identity-provider slot, task service, error envelope handlers, and health endpoint. Routes live in `backend/src/pe_agent/api/routes/analysis.py`; Pydantic wire schemas are in `backend/src/pe_agent/api/schemas.py`; identity normalization and permission checks are in `backend/src/pe_agent/api/dependencies.py`.

The API creates or resumes a durable task, then exposes snapshots, reports, review/archive operations, cancellation/retry, and replayable SSE. `TaskService` in `backend/src/pe_agent/application/task_service.py` owns transaction boundaries and service-level visibility, idempotency, review revision, archive, report-version, and cursor rules. Routes must translate domain/service failures to the existing error envelope rather than leaking persistence details.

### Worker and analysis pipeline

`backend/src/pe_agent/worker/service.py` claims tasks through a lease/fence-aware coordinator, runs `YieldDropWorkflow`, optionally requests a Jev decision, composes and validates a report, and atomically finalizes the task and durable events. The worker deliberately receives verified tenant/user/permission/entity scope from the task; it must not broaden that scope from adapter-returned Case data.

`backend/src/pe_agent/application/yield_drop_workflow.py` orchestrates read-only platform calls through the `PlatformDataPort`. It builds canonical domain request objects, checks Case version and related-entity authorization, batches tool calls, and returns `WorkflowCollection`. Platform implementations belong behind `backend/src/pe_agent/ports/` and `backend/src/pe_agent/adapters/`; the mock adapter is deterministic and synthetic, while the platform adapter is a template until official customer contracts exist.

`backend/src/pe_agent/application/reporting.py` composes the canonical report and performs JSON Schema plus semantic validation. Domain models in `backend/src/pe_agent/domain/` are the internal contract; do not mirror raw customer dictionaries into them. Evidence preserves source/quality/entity references and reports must bind task, report version, Case ID, and Case version to canonical inputs.

Decision integrations implement `DecisionPort`. Recorded decisions are loaded from synthetic fixtures; the TypeSafe adapter is opt-in and is used only for the constrained Choice/Score/Noul primitives. Jev does not select credentials, URLs, identities, tools, or customer-platform calls.

### Persistence and concurrency

SQLAlchemy models are in `backend/src/pe_agent/adapters/persistence/models.py`; repositories and row/advisory-lock/CAS operations are in `repositories.py`; schema creation/migrations are under `backend/alembic/`. Tasks and events are durable, report finalization is transactional, leases use fencing tokens, and review/archive idempotency is task-scoped. Preserve the database lifecycle CHECK constraints and test concurrency against real PostgreSQL where behavior depends on locking or rollback.

### Frontend state and host integration

The Vue/Pinia frontend is under `frontend/src/`. `src/store/caseAnalysis.ts` is the state boundary: it coordinates the host-neutral client, task/report/review/archive caches, request epochs, recovery storage, SSE reconnect/cursor handling, and terminal state transitions. Components such as `CaseAnalysisDrawer.vue` and `EngineerReviewForm.vue` render that state and emit user intent; `src/api/client.ts` maps the HTTP/SSE wire contract. Keep the host integration neutral through the client/host interfaces in `src/types.ts`.

SSE is replayable rather than a one-shot UI notification: preserve sequence ordering, cursor recovery, heartbeat behavior, terminal closure, and permission revalidation when changing either client or server code. Review form hydration must not mark saved data dirty or leak values between tasks/report versions.

### Deployment shape

`deploy/compose.yaml` defines PostgreSQL, migration, API, worker, and frontend services. Backend and frontend runtime containers are multi-stage/non-root and use read-only filesystems with narrowly scoped tmpfs paths. `deploy/helm/pe-agent/` contains the Kubernetes chart and profile values. `scripts/validate_deploy.py`, CI, and preflight encode the supported profile/deployment invariants; update those checks when deployment behavior intentionally changes.

## Change guidance

- Keep synthetic/mock paths explicit in names, responses, fixtures, and documentation; never present mock success as production readiness.
- For authorization changes, trace the complete path from verified identity to `RequestScope`, task persistence, worker scope, adapter requests, evidence entity references, and report validation.
- For API changes, update the Pydantic schema, frontend types/client/store, contract tests, and relevant documentation together.
- For persistence changes, update SQLAlchemy models, Alembic migration, repository transaction behavior, and PostgreSQL integration tests together.
- After completing a task, update [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) and [docs/07-development/todo.md](docs/07-development/todo.md), run applicable validation, and leave the worktree state/report accurate.
