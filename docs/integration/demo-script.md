# Mock-First Demo Script

This demo uses deterministic synthetic manufacturing evidence and recorded synthetic Jev decisions. It does not connect to a customer platform.

## Start

```sh
docker compose --env-file deploy/profiles/mock-recorded.env -f deploy/compose.yaml -f deploy/compose.mock-recorded.yaml up --build
```

Wait for PostgreSQL, migration, API, worker, and frontend health checks, then open the demo URL printed by Compose. The Case table and every source shown are synthetic.

## Golden path

1. Select `CASE-20260920-001` (`pressure-drift-success`).
2. Choose **AI Analysis** and verify one task is created.
3. Watch the fixed phases advance through context, baseline, process data, comparison, hypotheses, and report validation.
4. Verify the report labels observations separately from inferences and every conclusion links to evidence.
5. Open an evidence source through the demo host callback.
6. Submit an `INCONCLUSIVE`, `CONFIRMED`, or `CORRECTED` review. Verify Helpful remains an independent field.
7. Refresh the browser and verify the same task and review are restored.
8. Leave Case Book archive disabled.

Optional API smoke:

```sh
python scripts/smoke_test.py --base-url http://localhost:8000 --case-id CASE-20260920-001
```

The smoke test is read-only with respect to manufacturing systems and does not archive unless explicitly enabled.

## Failure paths

| Scenario | Expected behavior |
|---|---|
| `fdc-timeout` | Analysis reaches `PARTIAL_RESULT`; a report remains available, FDC is named as unavailable, and uncertainty/gaps remain visible. |
| `insufficient-evidence` | Analysis ends `FAILED` when no trustworthy report can be assembled; the UI offers a retry rather than a fabricated conclusion. |
| `permission-denied` | API returns the standard authorization error without creating or exposing a task; the UI requests host auth recovery when applicable. |
| `version-conflict` | Create returns `409 CASE_VERSION_CONFLICT`; the UI asks the engineer to refresh the Case and does not silently analyze stale data. |
| Browser refresh | Snapshot recovery resumes the authorized task; SSE sequence deduplication prevents duplicate progress or reports. |

## Stop

```sh
docker compose --env-file deploy/profiles/mock-recorded.env -f deploy/compose.yaml -f deploy/compose.mock-recorded.yaml down
```

If volumes were used, preserve them when demonstrating restart recovery. Removing volumes deletes the synthetic demo database and is not part of the normal demo flow.
