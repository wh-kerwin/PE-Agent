# Mock-First Platform Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-shaped Yield Drop analysis vertical slice with deterministic synthetic data now, while making future PE Duty / Engineer Platform integration an adapter replacement instead of a core rewrite.

**Architecture:** Run an embeddable Vue feature against a standalone analysis service. Keep canonical domain types independent from customer DTOs and place platform data, TypeSafe Jev, persistence, identity, and Case Book behind ports. Ship deterministic mock adapters, shared adapter contract tests, deployment profiles, preflight checks, and an FDE runbook before implementing any customer adapter.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16, httpx, pytest; Vue 3, TypeScript, Vite, Pinia, Arco Design Vue, Vitest, Testing Library, Playwright; Docker Compose, Helm 3, Kubernetes; TypeSafe System One HTTP API.

---

## Execution Rules

Implement in a dedicated Git worktree. Follow [PRD V1.1](../01-product/PRD-V1.md), [business API V1](../04-api/api-spec.md), [SSE V1](../04-api/sse-events.md), and [Analysis Report Schema](../../agent/schemas/analysis-report.schema.json). Treat them as versioned contracts.

Do not use production credentials or customer data. Every fixture and recorded model response must have `synthetic: true`. Do not invent customer API fields. A production profile must fail at startup when its adapter is not configured; it must never fall back to mock data.

Use this target boundary:

```text
Host Dashboard
  -> embeddable frontend feature
  -> Case Analysis API / SSE
  -> durable workflow
  -> PlatformDataPort / DecisionPort / CaseBookPort
  -> Mock adapters now; customer adapters later
```

## Milestone Gates

| Gate | Exit condition | External dependency |
|---|---|---|
| G1 Contracts | Canonical models and shared adapter contracts pass | None |
| G2 Mock vertical slice | Case row → task → SSE → report → review works | None |
| G3 Jev | Recorded and live adapters share one decision contract | API key for live smoke only |
| G4 FDE package | Compose/Helm, preflight, smoke, mapping and rollback are usable | None |
| G5 Real platform | Customer adapter passes contracts and shadow validation | Official API/IAM/data access |

G1–G4 are the current scope. G5 starts only after official documentation and sanitized payloads arrive.

---

### Task 1: Create the Worktree and Baseline

**Files:**
- Verify: `README.md`
- Verify: `scripts/validate_contracts.py`

**Step 1: Create a dedicated worktree**

```bash
git worktree add ../PE-Agent-implementation -b feat/mock-first-vertical-slice
```

**Step 2: Install current validation dependencies**

```bash
python -m pip install -r scripts/requirements.txt
```

**Step 3: Run baseline validation**

```bash
python scripts/validate_contracts.py
```

Expected: `Contract validation passed`.

**Step 4: Verify a clean starting point**

```bash
git status --short
```

Expected: no changes in the implementation worktree.

---

### Task 2: Scaffold the Backend Service

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/pe_agent/__init__.py`
- Create: `backend/src/pe_agent/main.py`
- Create: `backend/src/pe_agent/config.py`
- Create: `backend/tests/unit/test_health.py`

**Step 1: Write a failing liveness test**

```python
from fastapi.testclient import TestClient
from pe_agent.main import create_app


def test_liveness_has_no_external_dependencies() -> None:
    response = TestClient(create_app()).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Verify it fails**

```bash
python -m pytest backend/tests/unit/test_health.py -q
```

Expected: FAIL because `pe_agent.main` does not exist.

**Step 3: Implement the minimum service**

Use `src` layout and `pydantic-settings` with prefix `PE_AGENT_`. Add FastAPI, Uvicorn, Pydantic, SQLAlchemy, asyncpg, Alembic, httpx, jsonschema, pytest, pytest-asyncio, testcontainers, Ruff, and mypy. `/health/live` must not call a database or model.

**Step 4: Run checks**

```bash
python -m pytest backend/tests/unit/test_health.py -q
python -m ruff check backend/src backend/tests
python -m mypy backend/src
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend
git commit -m "build: scaffold case analysis service"
```

---

### Task 3: Define Canonical Domain Models

**Files:**
- Create: `backend/src/pe_agent/domain/case.py`
- Create: `backend/src/pe_agent/domain/evidence.py`
- Create: `backend/src/pe_agent/domain/task.py`
- Create: `backend/src/pe_agent/domain/report.py`
- Create: `backend/tests/unit/domain/test_models.py`

**Step 1: Write failing tests**

Test that Case requires ID, version, `YIELD_DROP`, timezone-aware timestamps, and at least one Lot. Test that Evidence requires source, entity references, event/retrieval times, and quality. Test that task execution status and engineer review status are independent. Test that 96% to 82% equals 14 percentage points.

**Step 2: Verify failure**

```bash
python -m pytest backend/tests/unit/domain/test_models.py -q
```

**Step 3: Implement strict Pydantic models**

Use `extra="forbid"`. Use snake_case internally and camelCase only in API DTOs. Represent unknown data as `None` or an explicit gap, never numeric zero. Match task statuses in the PRD.

**Step 4: Run tests**

```bash
python -m pytest backend/tests/unit/domain/test_models.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/pe_agent/domain backend/tests/unit/domain
git commit -m "feat: define canonical analysis domain"
```

---

### Task 4: Define Adapter Ports and Shared Contract Tests

**Files:**
- Create: `backend/src/pe_agent/ports/platform.py`
- Create: `backend/src/pe_agent/ports/decisions.py`
- Create: `backend/src/pe_agent/ports/casebook.py`
- Create: `backend/src/pe_agent/ports/repositories.py`
- Create: `backend/tests/contract/platform_adapter_contract.py`
- Create: `backend/tests/contract/decision_adapter_contract.py`

**Step 1: Write reusable platform contract tests**

Every adapter must prove authorization scope, timezone-aware timestamps, units, source IDs, distinct partial/unavailable results, maximum time windows, result limits, and read-only capability.

**Step 2: Write reusable decision contract tests**

Every decision adapter must normalize Choice, Score, and Noul; preserve requested/resolved model, question version, distributions, confidence rules, usage, timeout, and retryable errors.

**Step 3: Define typed Protocols**

`PlatformDataPort` must expose only:

```python
async def get_case_context(request: CaseContextRequest) -> CaseContext: ...
async def get_lot_yield(request: LotYieldRequest) -> ToolResult[YieldEvidence]: ...
async def get_tool_events(request: ToolEventsRequest) -> ToolResult[ToolEventEvidence]: ...
async def get_recipe_snapshot(request: RecipeRequest) -> ToolResult[RecipeEvidence]: ...
async def get_spc_evidence(request: SpcRequest) -> ToolResult[SpcEvidence]: ...
async def get_fdc_evidence(request: FdcRequest) -> ToolResult[FdcEvidence]: ...
async def search_similar_cases(request: SimilarCasesRequest) -> ToolResult[HistoricalCaseEvidence]: ...
```

Return canonical types, never raw customer dictionaries. Supply `RequestScope` from verified server identity, never the request body.

**Step 4: Type-check**

```bash
python -m mypy backend/src
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/pe_agent/ports backend/tests/contract
git commit -m "feat: define platform integration contracts"
```

---

### Task 5: Build Deterministic Synthetic Scenarios

**Files:**
- Create: `backend/fixtures/scenarios/pressure-drift-success.json`
- Create: `backend/fixtures/scenarios/recipe-change.json`
- Create: `backend/fixtures/scenarios/conflicting-sources.json`
- Create: `backend/fixtures/scenarios/fdc-timeout.json`
- Create: `backend/fixtures/scenarios/insufficient-evidence.json`
- Create: `backend/fixtures/scenarios/version-conflict.json`
- Create: `backend/fixtures/scenarios/permission-denied.json`
- Create: `backend/fixtures/scenarios/history-mismatch.json`
- Create: `backend/src/pe_agent/adapters/platform/mock.py`
- Create: `backend/tests/contract/test_mock_platform.py`

**Step 1: Declare expected behavior in each fixture**

Include `synthetic: true`, expected task outcome, unavailable sources, evidence IDs, and permission profile. Do not include company/fab names, internal hosts, or realistic credentials.

**Step 2: Run the shared platform contract and verify failure**

```bash
python -m pytest backend/tests/contract/test_mock_platform.py -q
```

**Step 3: Implement `MockPlatformAdapter`**

Validate fixtures on load. Inject timeout/conflict/denial from fixture declarations, without randomness or real sleeps. Use an injectable clock.

**Step 4: Run all scenario contracts**

```bash
python -m pytest backend/tests/contract/test_mock_platform.py -q
```

Expected: PASS for all eight scenarios.

**Step 5: Commit**

```bash
git add backend/fixtures backend/src/pe_agent/adapters/platform backend/tests/contract
git commit -m "feat: add deterministic manufacturing simulator"
```

---

### Task 6: Add Durable PostgreSQL State

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/versions/0001_analysis_core.py`
- Create: `backend/src/pe_agent/adapters/persistence/models.py`
- Create: `backend/src/pe_agent/adapters/persistence/repositories.py`
- Create: `backend/src/pe_agent/adapters/persistence/session.py`
- Create: `backend/tests/integration/test_task_repository.py`

**Step 1: Write failing Testcontainers tests**

Cover idempotent creation, unique `(task_id, sequence)`, immutable reports, review revisions, task/outbox atomicity, worker leases, and compare-and-set terminal transitions.

**Step 2: Verify failure**

```bash
python -m pytest backend/tests/integration/test_task_repository.py -q
```

**Step 3: Implement the logical schema**

Follow [database schema](../05-data/database-schema.md). Keep SQLAlchemy models inside the adapter. Store large tool results by encrypted/object-storage reference later; persist hashes and safe metadata now.

**Step 4: Run migration and tests**

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m pytest backend/tests/integration/test_task_repository.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend
git commit -m "feat: persist tasks reports and events"
```

---

### Task 7: Implement Task API and Durable Worker

**Files:**
- Create: `backend/src/pe_agent/api/dependencies.py`
- Create: `backend/src/pe_agent/api/schemas.py`
- Create: `backend/src/pe_agent/api/routes/analysis.py`
- Create: `backend/src/pe_agent/application/task_service.py`
- Create: `backend/src/pe_agent/application/yield_drop_workflow.py`
- Create: `backend/src/pe_agent/worker/runner.py`
- Create: `backend/src/pe_agent/worker/claim.py`
- Create: `backend/tests/integration/test_analysis_api.py`
- Create: `backend/tests/integration/test_worker_recovery.py`

**Step 1: Write API tests**

Cover 202 create, idempotency replay, running-task reuse, GET snapshot, version conflict, unsupported Case, permission denial, retry creates new task, and idempotent cancel.

**Step 2: Write workflow/recovery tests**

Cover fixed phase order from `agent/workflow/yield-drop.workflow.json`, tool/replan budgets, partial sources, timeout, cancellation, expired lease reclaim, and rejection of late results after terminal state.

**Step 3: Verify failure**

```bash
python -m pytest backend/tests/integration/test_analysis_api.py backend/tests/integration/test_worker_recovery.py -q
```

**Step 4: Implement API and worker**

Create task plus outbox in one transaction. Claim work with `FOR UPDATE SKIP LOCKED`, lease deadline, and fencing token. Provide a development-only server-side `MockIdentityProvider`; never accept tenant/user/role from JSON. Persist each committed phase event.

**Step 5: Run tests and commit**

```bash
python -m pytest backend/tests/integration/test_analysis_api.py backend/tests/integration/test_worker_recovery.py -q
git add backend
git commit -m "feat: run durable yield drop tasks"
```

---

### Task 8: Validate Evidence and Assemble Reports

**Files:**
- Create: `backend/src/pe_agent/application/evidence_service.py`
- Create: `backend/src/pe_agent/application/report_service.py`
- Create: `backend/src/pe_agent/application/report_validation.py`
- Create: `backend/src/pe_agent/adapters/schema/report_schema.py`
- Create: `backend/tests/unit/application/test_report_service.py`

**Step 1: Write failing report tests**

Test numeric derivation, reference existence, chronological timeline, authorized entities, source-link generation, hypothesis support/contradiction/gaps, uncertainty for partial reports, and no confirmed-root-cause language.

Add negative tests for hallucinated evidence IDs, unit mismatch, unauthorized entities, model-generated URLs, and missing data represented as zero.

**Step 2: Verify failure**

```bash
python -m pytest backend/tests/unit/application/test_report_service.py -q
```

**Step 3: Implement deterministic assembly**

Build report fields in code from validated Evidence and decision results. Run JSON Schema validation, then semantic validation. Generate `rawRef` server-side from evidence IDs.

**Step 4: Run repository and service validation**

```bash
python scripts/validate_contracts.py
python -m pytest backend/tests/unit/application/test_report_service.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend
git commit -m "feat: assemble evidence-grounded reports"
```

---

### Task 9: Add Recorded and Live TypeSafe Jev Adapters

**Files:**
- Create: `backend/src/pe_agent/adapters/decisions/recorded.py`
- Create: `backend/src/pe_agent/adapters/decisions/typesafe.py`
- Create: `backend/src/pe_agent/adapters/decisions/questions.py`
- Create: `backend/tests/contract/test_recorded_decisions.py`
- Create: `backend/tests/unit/adapters/test_typesafe_adapter.py`
- Create: `backend/tests/live/test_typesafe_smoke.py`

**Step 1: Make recorded responses pass the shared contract**

Use `examples/jev-assessment.json` plus synthetic Choice and Noul fixtures. Preserve question-set and resolved-model versions.

**Step 2: Test the HTTP adapter with `httpx.MockTransport`**

Assert request fields are exactly `state`, `model`, `questions`. Test 401/422 without retry; bounded 429/529 retry; malformed response; timeout; cancellation; and secret redaction.

**Step 3: Implement adapters**

Default local profile is `recorded`. Live TypeSafe requires explicit enablement and `TYPESAFE_API_KEY`. Pin `jev-1.13.0` for the initial evaluation baseline and record the response model. Send only normalized Evidence summaries. Jev cannot choose URLs, credentials, identities, or raw platform calls.

**Step 4: Add opt-in live smoke**

Skip unless `RUN_TYPESAFE_LIVE=1`. Ask one synthetic Noul and log only version/usage. Never run it in ordinary CI.

**Step 5: Run tests and commit**

```bash
python -m pytest backend/tests/contract/test_recorded_decisions.py backend/tests/unit/adapters/test_typesafe_adapter.py -q
git add backend
git commit -m "feat: add TypeSafe System One decisions"
```

---

### Task 10: Add Replayable SSE, Review, and Mock Case Book

**Files:**
- Create: `backend/src/pe_agent/api/routes/events.py`
- Create: `backend/src/pe_agent/api/routes/review.py`
- Create: `backend/src/pe_agent/application/event_service.py`
- Create: `backend/src/pe_agent/application/review_service.py`
- Create: `backend/src/pe_agent/adapters/platform/mock_casebook.py`
- Create: `backend/tests/integration/test_sse.py`
- Create: `backend/tests/integration/test_review_api.py`

**Step 1: Write SSE tests**

Cover sequence order, `Last-Event-ID`, deduplication, cursor expiry, heartbeat with fake clock, permission recheck, terminal close, and background survival after disconnect.

**Step 2: Write review/archive tests**

Cover independent Helpful/review status, immutable AI report, review revision conflict, archive precondition, permission, idempotency, and retryable archive failure.

**Step 3: Implement from committed database events**

Use PostgreSQL for V1; do not add Redis. SSE sends report URL/version, not the report. Mock Case Book returns a stable synthetic archive ID and never changes Case or manufacturing state.

**Step 4: Run tests**

```bash
python -m pytest backend/tests/integration/test_sse.py backend/tests/integration/test_review_api.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend
git commit -m "feat: stream progress and record engineer review"
```

---

### Task 11: Build the Embeddable Vue Feature

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/features/case-analysis/index.ts`
- Create: `frontend/src/features/case-analysis/types.ts`
- Create: `frontend/src/features/case-analysis/api/client.ts`
- Create: `frontend/src/features/case-analysis/api/event-stream.ts`
- Create: `frontend/src/features/case-analysis/store.ts`
- Create: `frontend/src/features/case-analysis/components/CaseAnalysisAction.vue`
- Create: `frontend/src/features/case-analysis/components/CaseAnalysisDrawer.vue`
- Create: `frontend/src/features/case-analysis/components/AnalysisReport.vue`
- Create: `frontend/src/features/case-analysis/components/EngineerReviewForm.vue`
- Create: `frontend/src/demo/App.vue`
- Create: `frontend/tests/unit/case-analysis.spec.ts`
- Create: `frontend/tests/unit/store.spec.ts`

**Step 1: Write API/store tests**

Cover create/resume, error mapping, sequence deduplication, stale-task guard, snapshot recovery, cursor expiry, permission loss, and report fetch after `report_generated`.

**Step 2: Write component tests**

Cover button states, Drawer, stable loading layout, partial alert, evidence expansion, controlled source callback, hypothesis support/contradiction/gaps, plain-text rendering, Review, keyboard behavior, and mobile full-screen mode.

**Step 3: Verify failure**

```bash
npm --prefix frontend install
npm --prefix frontend run test:unit
```

**Step 4: Implement a host-neutral feature**

Export `CaseAnalysisAction`, `CaseAnalysisDrawer`, client, and types. Accept host callbacks for auth recovery and `openSource(rawRef)`. Do not hard-code host routes or store access tokens. The demo host is a synthetic Case Table, not a new Dashboard.

Follow [UI design](../06-frontend/ui-design.md). Never display Jev confidence as root-cause probability.

**Step 5: Run checks and commit**

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test:unit
npm --prefix frontend run build
git add frontend
git commit -m "feat: add embeddable case analysis drawer"
```

---

### Task 12: Add End-to-End Acceptance Scenarios

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/analysis-success.spec.ts`
- Create: `frontend/tests/e2e/analysis-partial.spec.ts`
- Create: `frontend/tests/e2e/analysis-recovery.spec.ts`
- Create: `scripts/run-e2e.ps1`

**Step 1: Write three failing E2E tests**

Test pressure-drift complete report/review, FDC timeout partial result, and browser refresh restoring the same task without duplication.

**Step 2: Add a deterministic runner**

Start PostgreSQL, API, worker, and demo UI on configured ports with readiness checks and cleanup. Use `mock + recorded`, never a live Jev key.

**Step 3: Run desktop/mobile and accessibility checks**

```bash
npm --prefix frontend run test:e2e
```

Expected: all scenarios pass on desktop and mobile with no critical accessibility violations.

**Step 4: Commit**

```bash
git add frontend scripts/run-e2e.ps1
git commit -m "test: cover mock workflows end to end"
```

---

### Task 13: Package Compose and Kubernetes Deployment

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `deploy/docker-compose.yml`
- Create: `deploy/.env.example`
- Create: `deploy/helm/pe-case-agent/Chart.yaml`
- Create: `deploy/helm/pe-case-agent/values.yaml`
- Create: `deploy/helm/pe-case-agent/templates/deployment-api.yaml`
- Create: `deploy/helm/pe-case-agent/templates/deployment-worker.yaml`
- Create: `deploy/helm/pe-case-agent/templates/service.yaml`
- Create: `deploy/helm/pe-case-agent/templates/configmap.yaml`
- Create: `deploy/helm/pe-case-agent/templates/networkpolicy.yaml`
- Create: `deploy/helm/pe-case-agent/templates/migration-job.yaml`
- Create: `scripts/validate_deploy.py`

**Step 1: Write failing manifest validation**

Require separate API/worker, probes, resources, non-root user, migration job, explicit platform/decision profiles, external PostgreSQL for Helm, no secret values, and SSE proxy buffering disabled.

**Step 2: Implement four profiles**

- `mock-recorded`: default demo.
- `mock-live-jev`: requires TypeSafe secret.
- `platform-shadow`: real data adapter, no Case Book write.
- `platform-production`: enabled only after readiness sign-off.

**Step 3: Validate artifacts**

```bash
docker compose -f deploy/docker-compose.yml config
helm lint deploy/helm/pe-case-agent
helm template pe-agent deploy/helm/pe-case-agent > rendered.yaml
python scripts/validate_deploy.py rendered.yaml
```

Expected: PASS with no committed secret.

**Step 4: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile deploy scripts/validate_deploy.py
git commit -m "ops: package FDE deployment profiles"
```

---

### Task 14: Build the FDE Integration Kit

**Files:**
- Create: `docs/integration/platform-discovery-checklist.md`
- Create: `docs/integration/field-mapping-template.md`
- Create: `docs/integration/fde-runbook.md`
- Create: `docs/integration/production-readiness-checklist.md`
- Create: `backend/src/pe_agent/adapters/platform/template.py`
- Create: `backend/tests/contract/test_platform_template.py`
- Create: `scripts/preflight.py`
- Create: `scripts/smoke_test.py`

**Step 1: Create a fail-fast adapter template**

It maps customer DTOs to canonical objects and raises `ADAPTER_NOT_CONFIGURED` until completed. A platform profile must never import or return mock fixtures.

**Step 2: Write preflight checks**

Check configuration, DB, endpoint reachability, IAM handshake, Case read permission, timezone/unit mapping, TypeSafe when enabled, and Case Book only when archive is enabled. Never print tokens or payloads.

**Step 3: Write a non-destructive smoke test**

Accept a dedicated test Case ID and validate create → SSE/GET → report → optional review. Archive is off by default. Manufacturing writes do not exist.

**Step 4: Document the FDE sequence**

1. Complete data classification and platform discovery.
2. Capture sanitized endpoint success/error payloads.
3. Fill field, enum, unit, timezone, permission, and SLA mappings.
4. Implement only the customer adapter package.
5. Run the shared platform contract suite.
6. Deploy `platform-shadow` with archive disabled.
7. Compare a golden Case set with PE engineers.
8. Enable Jev after data-egress approval and CJK evaluation.
9. Enable Review/Case Book after IAM and idempotency tests.
10. Promote with tested rollback and saved configuration.

**Step 5: Validate and commit**

```bash
python scripts/validate_contracts.py
python -m pytest backend/tests/contract -q
python scripts/preflight.py --profile mock-recorded
git add docs/integration backend/src/pe_agent/adapters/platform/template.py backend/tests/contract scripts
git commit -m "docs: add FDE platform integration kit"
```

Expected: mock preflight passes; platform template proves fail-fast behavior.

---

### Task 15: Add CI and Release Evidence

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `scripts/release_evidence.py`
- Create: `docs/integration/release-evidence-template.md`

**Step 1: Add required CI jobs**

Run repository contracts; backend lint/type/unit/integration; frontend type/unit/build; mock E2E; Compose/Helm validation; organization-approved dependency and secret scanning.

**Step 2: Generate release evidence**

Record Git SHA, schema/workflow/question/tool versions, image digests, test summaries, resolved test model, and deployment profile. Exclude credentials and manufacturing payloads.

**Step 3: Run the full local gate**

```bash
python scripts/validate_contracts.py
python -m pytest backend/tests -q
npm --prefix frontend run typecheck
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm --prefix frontend run test:e2e
helm lint deploy/helm/pe-case-agent
```

Expected: PASS in `mock-recorded` profile.

**Step 4: Commit**

```bash
git add .github scripts docs/integration
git commit -m "ci: enforce vertical slice release gates"
```

---

### Task 16: Final Demo and Handoff

**Files:**
- Modify: `README.md`
- Create: `docs/integration/demo-script.md`
- Create: `docs/integration/known-limitations.md`

**Step 1: Document one-command demo startup**

Use `mock-recorded` by default. State visibly that manufacturing data and Jev responses are synthetic.

**Step 2: Run from a clean checkout**

```bash
docker compose -f deploy/docker-compose.yml up --build
python scripts/smoke_test.py --base-url http://localhost:8000 --case-id CASE-20260920-001
```

Expected: task reaches COMPLETED, references resolve, Review succeeds, and archive remains disabled.

**Step 3: Demonstrate failure paths**

Run FDC timeout, insufficient evidence, permission denied, and version conflict. Record the expected UI/API behavior.

**Step 4: Record honest limitations**

State that no real platform, IAM, manufacturing source, Case Book, or production Jev workload has been validated. Link each limitation to G5 rather than presenting mock success as production readiness.

**Step 5: Final validation and commit**

```bash
python scripts/validate_contracts.py
git status --short
git add README.md docs/integration
git commit -m "docs: hand off mock-first vertical slice"
```

---

## First Real Platform Adapter Procedure

When API documentation and sanitized payloads arrive, create one adapter package:

```text
backend/src/pe_agent/adapters/platform/customer_a/
├── client.py
├── dto.py
├── mapping.py
├── adapter.py
└── errors.py
```

Map customer identifiers, statuses, units, and timestamps at this boundary. Do not alter canonical models merely to mirror the platform DTO. If a true domain concept is missing, version the canonical model, fixtures, report schema, frontend types, and shared contract together.

The adapter must pass the same platform contract suite as Mock plus recorded endpoint-response tests. Deploy first as `platform-shadow`, with read-only data access, Case Book disabled, and Jev disabled until approved. Compare the agreed golden Case set with PE engineers before enabling any external write.

## Production Readiness Owners

FDE must record named owners for platform API, IAM, manufacturing data, TypeSafe/data egress, Kubernetes/DB, and PE acceptance. Promotion requires adapter contract results, golden Case evaluation, CJK evaluation, load/SSE recovery, audit sampling, backup/restore, retention/ZDR decision, and a tested rollback.

## Definition of Done

- Eight deterministic scenarios execute without customer dependencies.
- Browser creates, restores, reads, and reviews an analysis.
- Task/event/report state survives API and worker restarts.
- Every conclusion traces to authorized Evidence.
- Recorded and live Jev adapters implement one DecisionPort.
- Jev outage has an explicit partial-result path.
- Vue feature exports a host integration boundary.
- Compose and Helm pass validation.
- Adapter template, contract tests, mapping worksheet, preflight, smoke test, shadow profile, and rollback instructions are usable by an FDE.
- Production profile cannot silently use mock data.

## Claude Execution Prompt

```text
Read docs/plans/2026-09-20-mock-first-platform-integration.md and execute it with the executing-plans workflow. Work in a dedicated worktree. Implement tasks in order, run every specified test, and commit after each task. Treat docs/01-product/PRD-V1.md, docs/04-api, agent/schemas, agent/tools, and agent/workflow as versioned contracts. Stop at a milestone gate if a required test cannot pass and report the concrete blocker. Preserve the platform adapter boundary. Do not invent real platform fields, credentials, endpoints, or customer data.
```
