from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from pe_agent.api.dependencies import Identity
from pe_agent.api.routes.analysis import _event_stream
from pe_agent.api.schemas import (
    ArchiveResponse,
    ReviewResponse,
    TaskAccepted,
    TaskSnapshot,
)
from pe_agent.application.task_service import (
    ArchiveDisabledError,
    RetryNotAllowedError,
    StreamBatch,
    StreamEvent,
    TaskNotFoundError,
)
from pe_agent.config import Settings
from pe_agent.main import create_app

NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
IDENTITY = Identity(
    tenant_id="synthetic-tenant",
    user_id="synthetic-engineer",
    permissions=frozenset(
        {"case.read", "case.analysis.review", "casebook.write"}
    ),
    authorized_entity_ids=frozenset({"SYN-CASE"}),
    permission_scope_hash="scope-hash",
)


class FakeTaskService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: Exception | None = None

    async def create_or_resume(self, **kwargs: Any) -> TaskAccepted:
        self._record("create", kwargs)
        return TaskAccepted(
            task_id="ANA-SYN-1",
            case_id=kwargs["case_id"],
            case_version=kwargs["case_version"],
            status="CREATED",
            reused=False,
            stream_url="/api/ai/case-analysis/ANA-SYN-1/stream",
        )

    async def get_snapshot(self, **kwargs: Any) -> TaskSnapshot:
        self._record("get", kwargs)
        return _snapshot()

    async def get_latest_snapshot(self, **kwargs: Any) -> TaskSnapshot:
        self._record("latest", kwargs)
        return _snapshot()

    async def retry(self, **kwargs: Any) -> TaskAccepted:
        self._record("retry", kwargs)
        return TaskAccepted(
            task_id="ANA-SYN-2",
            case_id="SYN-CASE",
            case_version="1",
            status="CREATED",
            reused=False,
            stream_url="/api/ai/case-analysis/ANA-SYN-2/stream",
        )

    async def cancel(self, **kwargs: Any) -> TaskSnapshot:
        self._record("cancel", kwargs)
        return _snapshot(status="CANCELLED")

    async def submit_review(self, **kwargs: Any) -> ReviewResponse:
        self._record("review", kwargs)
        body = kwargs["request"]
        return ReviewResponse(
            task_id="ANA-SYN-1",
            report_version=body.report_version,
            review_status=body.review_status,
            helpful=body.helpful,
            confirmed_hypothesis_id=body.confirmed_hypothesis_id,
            actual_root_cause=body.actual_root_cause,
            comment=body.comment,
            idempotency_key=body.idempotency_key,
            review_revision=1,
            created_at=NOW,
        )

    async def archive_casebook(self, **kwargs: Any) -> ArchiveResponse:
        self._record("archive", kwargs)
        return ArchiveResponse(
            archive_id="CB-SYN-1",
            status="ARCHIVED",
            review_revision=kwargs["review_revision"],
            message="Synthetic Case Book archive; no customer system was called.",
        )

    async def stream_batch(self, **kwargs: Any) -> StreamBatch:
        self._record("stream", kwargs)
        return StreamBatch(
            events=(
                StreamEvent(
                    sequence=2,
                    type="analysis_completed",
                    payload={"message": "Synthetic completion"},
                    occurred_at=NOW,
                ),
            ),
            terminal=True,
            latest_sequence=2,
        )

    def _record(self, operation: str, kwargs: dict[str, Any]) -> None:
        self.calls.append((operation, kwargs))
        if self.error is not None:
            raise self.error


def _scope_hash(identity: Identity) -> str:
    value = ":".join(
        (
            identity.tenant_id,
            identity.user_id,
            ",".join(sorted(identity.permissions)),
            ",".join(sorted(identity.authorized_entity_ids)),
        )
    )
    return sha256(value.encode()).hexdigest()


def _snapshot(*, status: str = "INVESTIGATING") -> TaskSnapshot:
    return TaskSnapshot(
        task_id="ANA-SYN-1",
        case_id="SYN-CASE",
        case_version="1",
        status=status,
        phase=None if status == "CANCELLED" else "investigate",
        progress=100 if status == "CANCELLED" else 20,
        latest_event_id="2",
        created_at=NOW,
        updated_at=NOW,
        completed_at=NOW if status == "CANCELLED" else None,
        versions={"agent": "v1", "model": "recorded", "prompt": "v1", "schema": "v1"},
    )


def _client(
    service: FakeTaskService,
    *,
    production: bool = False,
    identity: Identity = IDENTITY,
) -> TestClient:
    settings = Settings(environment="production" if production else "test")
    app = create_app(settings)
    app.state.task_service = service
    if not production:
        app.state.identity_provider = lambda: identity
    return TestClient(app)


def test_create_uses_verified_identity_scope() -> None:
    service = FakeTaskService()

    response = _client(service).post(
        "/api/ai/case-analysis",
        json={"caseId": "SYN-CASE", "caseVersion": "1", "idempotencyKey": "idem-1"},
    )

    assert response.status_code == 202
    assert response.json()["streamUrl"].endswith("/ANA-SYN-1/stream")
    assert service.calls == [
        (
            "create",
            {
                "tenant_id": IDENTITY.tenant_id,
                "user_id": IDENTITY.user_id,
                "permissions": IDENTITY.permissions,
                "authorized_entity_ids": IDENTITY.authorized_entity_ids,
                "permission_scope_hash": _scope_hash(IDENTITY),
                "case_id": "SYN-CASE",
                "case_version": "1",
                "idempotency_key": "idem-1",
            },
        )
    ]


def test_request_body_cannot_supply_identity_fields() -> None:
    service = FakeTaskService()

    response = _client(service).post(
        "/api/ai/case-analysis",
        json={
            "caseId": "SYN-CASE",
            "caseVersion": "1",
            "idempotencyKey": "idem-1",
            "tenantId": "attacker-tenant",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert service.calls == []


def test_create_rejects_unauthorized_case_before_service() -> None:
    service = FakeTaskService()

    response = _client(service).post(
        "/api/ai/case-analysis",
        json={"caseId": "OTHER-CASE", "caseVersion": "1", "idempotencyKey": "idem-1"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CASE_ACCESS_DENIED"
    assert service.calls == []


def test_task_lookup_hides_cross_scope_and_missing_tasks() -> None:
    service = FakeTaskService()
    service.error = TaskNotFoundError("ANA-OTHER")

    response = _client(service).get("/api/ai/case-analysis/ANA-OTHER")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"
    assert response.json()["error"]["details"] == {}


def test_latest_retry_and_cancel_forward_current_scope() -> None:
    service = FakeTaskService()
    client = _client(service)

    latest = client.get("/api/ai/case-analysis?caseId=SYN-CASE&latest=true")
    retried = client.post(
        "/api/ai/case-analysis/ANA-SYN-1/retry",
        json={"idempotencyKey": "retry-1"},
    )
    cancelled = client.post("/api/ai/case-analysis/ANA-SYN-1/cancel", json={})

    assert latest.status_code == 200
    assert retried.status_code == 202
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert [call[0] for call in service.calls] == ["latest", "retry", "cancel"]
    assert all(
        call[1]["permission_scope_hash"] == _scope_hash(IDENTITY)
        for call in service.calls
    )


def test_retry_rejects_non_retryable_status() -> None:
    service = FakeTaskService()
    service.error = RetryNotAllowedError("COMPLETED")

    response = _client(service).post(
        "/api/ai/case-analysis/ANA-SYN-1/retry",
        json={"idempotencyKey": "retry-1"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RETRY_NOT_ALLOWED"


def test_review_uses_verified_reviewer_and_scope() -> None:
    service = FakeTaskService()

    response = _client(service).post(
        "/api/ai/case-analysis/ANA-SYN-1/review",
        json={
            "reportVersion": 1,
            "reviewStatus": "CORRECTED",
            "helpful": True,
            "confirmedHypothesisId": None,
            "actualRootCause": "Synthetic calibration drift",
            "comment": "Verified with synthetic evidence.",
            "idempotencyKey": "review-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "taskId": "ANA-SYN-1",
        "reportVersion": 1,
        "reviewStatus": "CORRECTED",
        "helpful": True,
        "confirmedHypothesisId": None,
        "actualRootCause": "Synthetic calibration drift",
        "comment": "Verified with synthetic evidence.",
        "idempotencyKey": "review-1",
        "reviewRevision": 1,
        "createdAt": "2026-09-20T10:00:00Z",
    }
    _, arguments = service.calls[0]
    assert arguments["reviewer_id"] == IDENTITY.user_id
    assert arguments["permission_scope_hash"] == _scope_hash(IDENTITY)


def test_review_requires_dedicated_permission() -> None:
    service = FakeTaskService()
    identity = Identity(
        tenant_id=IDENTITY.tenant_id,
        user_id=IDENTITY.user_id,
        permissions=frozenset({"case.read"}),
        authorized_entity_ids=IDENTITY.authorized_entity_ids,
        permission_scope_hash=IDENTITY.permission_scope_hash,
    )

    response = _client(service, identity=identity).post(
        "/api/ai/case-analysis/ANA-SYN-1/review",
        json={
            "reportVersion": 1,
            "reviewStatus": "INCONCLUSIVE",
            "idempotencyKey": "review-1",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert service.calls == []


def test_archive_returns_explicit_synthetic_result() -> None:
    service = FakeTaskService()

    response = _client(service).post(
        "/api/ai/case-analysis/ANA-SYN-1/casebook",
        json={"reviewRevision": 1, "idempotencyKey": "archive-1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "archiveId": "CB-SYN-1",
        "status": "ARCHIVED",
        "reviewRevision": 1,
        "message": "Synthetic Case Book archive; no customer system was called.",
    }


def test_archive_disabled_is_explicit() -> None:
    service = FakeTaskService()
    service.error = ArchiveDisabledError("ANA-SYN-1")

    response = _client(service).post(
        "/api/ai/case-analysis/ANA-SYN-1/casebook",
        json={"reviewRevision": 1, "idempotencyKey": "archive-1"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CASEBOOK_ARCHIVE_DISABLED"


def test_stream_replays_after_string_cursor_and_closes_on_terminal() -> None:
    service = FakeTaskService()

    response = _client(service).get(
        "/api/ai/case-analysis/ANA-SYN-1/stream",
        headers={"Last-Event-ID": "1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-store"
    assert response.headers["x-accel-buffering"] == "no"
    assert "id: 2\nevent: analysis_completed\ndata: " in response.text
    data = response.text.split("data: ", maxsplit=1)[1].strip()
    assert json.loads(data) == {
        "schemaVersion": "1.0.0",
        "taskId": "ANA-SYN-1",
        "sequence": 2,
        "occurredAt": "2026-09-20T10:00:00Z",
        "payload": {"message": "Synthetic completion"},
    }
    assert service.calls[0][1]["after_sequence"] == 1


def test_stream_rejects_non_numeric_cursor_before_service() -> None:
    service = FakeTaskService()

    response = _client(service).get(
        "/api/ai/case-analysis/ANA-SYN-1/stream",
        headers={"Last-Event-ID": "not-a-cursor"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert service.calls == []


class StreamRequest:
    def __init__(self, provider: Any) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(identity_provider=provider))

    async def is_disconnected(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_stream_revalidates_before_emitting_a_pending_batch() -> None:
    revoked = Identity(
        tenant_id=IDENTITY.tenant_id,
        user_id=IDENTITY.user_id,
        permissions=frozenset(),
        authorized_entity_ids=IDENTITY.authorized_entity_ids,
        permission_scope_hash="ignored",
    )
    request = cast(Request, StreamRequest(lambda: revoked))
    pending = StreamBatch(
        events=(
            StreamEvent(
                sequence=2,
                type="analysis_completed",
                payload={"message": "must not be emitted"},
                occurred_at=NOW,
            ),
        ),
        terminal=True,
        latest_sequence=2,
    )
    stream = _event_stream(
        request=request,
        identity=IDENTITY,
        service=cast(Any, FakeTaskService()),
        task_id="ANA-SYN-1",
        cursor=1,
        initial=pending,
        poll_seconds=0.001,
        heartbeat_seconds=1.0,
        permission_recheck_seconds=0.0,
    )

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


class IdleTaskService(FakeTaskService):
    async def stream_batch(self, **kwargs: Any) -> StreamBatch:
        del kwargs
        return StreamBatch(events=(), terminal=False, latest_sequence=1)


@pytest.mark.asyncio
async def test_stream_emits_heartbeat_while_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    service = IdleTaskService()
    request = cast(Request, StreamRequest(lambda: IDENTITY))
    idle = StreamBatch(events=(), terminal=False, latest_sequence=1)
    times = iter((0.0, 0.0, 2.0, 2.0, 2.0, 2.0))
    monkeypatch.setattr("pe_agent.api.routes.analysis.monotonic", lambda: next(times))
    stream = cast(
        AsyncGenerator[str, None],
        _event_stream(
            request=request,
            identity=IDENTITY,
            service=cast(Any, service),
            task_id="ANA-SYN-1",
            cursor=1,
            initial=idle,
            poll_seconds=0.001,
            heartbeat_seconds=1.0,
            permission_recheck_seconds=10.0,
        ),
    )

    assert await anext(stream) == ": heartbeat\n\n"
    await stream.aclose()


def test_production_requires_host_identity_provider() -> None:
    response = _client(FakeTaskService(), production=True).get(
        "/api/ai/case-analysis/ANA-SYN-1",
        headers={
            "X-PE-Tenant": "spoofed",
            "X-PE-User": "spoofed",
            "X-PE-Permissions": "admin",
            "X-PE-Entities": "SYN-CASE",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
