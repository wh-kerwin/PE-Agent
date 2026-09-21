from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from time import monotonic
from typing import Annotated, NoReturn, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from pe_agent.api.dependencies import (
    Identity,
    get_identity,
    refresh_identity,
    require_entity,
    require_permission,
)
from pe_agent.api.schemas import (
    ArchiveRequest,
    ArchiveResponse,
    CreateAnalysisRequest,
    ErrorBody,
    ErrorEnvelope,
    RetryRequest,
    ReviewRequest,
    ReviewResponse,
    TaskAccepted,
    TaskSnapshot,
)
from pe_agent.application.task_service import (
    ArchiveDisabledError,
    EventCursorError,
    IdempotencyConflictError,
    ReportVersionConflictError,
    RetryNotAllowedError,
    ReviewRevisionConflictError,
    ReviewValidationError,
    StreamBatch,
    StreamEvent,
    TaskNotFoundError,
    TaskService,
)

router = APIRouter(prefix="/api/ai/case-analysis", tags=["case-analysis"])
IdentityDependency = Annotated[Identity, Depends(get_identity)]


def get_task_service(request: Request) -> TaskService:
    return cast(TaskService, request.app.state.task_service)


ServiceDependency = Annotated[TaskService, Depends(get_task_service)]


@router.post("", response_model=TaskAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    body: CreateAnalysisRequest,
    identity: IdentityDependency,
    service: ServiceDependency,
) -> TaskAccepted:
    require_permission(identity, "case.read")
    require_entity(identity, body.case_id)
    try:
        return await service.create_or_resume(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            permissions=identity.permissions,
            authorized_entity_ids=identity.authorized_entity_ids,
            permission_scope_hash=identity.permission_scope_hash,
            case_id=body.case_id,
            case_version=body.case_version,
            idempotency_key=body.idempotency_key,
        )
    except IdempotencyConflictError:
        _idempotency_conflict()


@router.get("", response_model=TaskSnapshot)
async def get_latest_analysis(
    identity: IdentityDependency,
    service: ServiceDependency,
    case_id: Annotated[str, Query(alias="caseId", min_length=1)],
    latest: Annotated[bool, Query()] = True,
) -> TaskSnapshot:
    if not latest:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST"})
    require_permission(identity, "case.read")
    require_entity(identity, case_id)
    try:
        return await service.get_latest_snapshot(
            case_id=case_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
        )
    except TaskNotFoundError:
        _not_found()


@router.get("/{task_id}", response_model=TaskSnapshot)
async def get_analysis(
    task_id: str,
    identity: IdentityDependency,
    service: ServiceDependency,
) -> TaskSnapshot:
    require_permission(identity, "case.read")
    try:
        return await service.get_snapshot(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
        )
    except TaskNotFoundError:
        _not_found()


@router.get("/{task_id}/report", response_model=None)
async def get_report(
    task_id: str,
    identity: IdentityDependency,
    service: ServiceDependency,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    require_permission(identity, "case.read")
    try:
        return await service.get_report(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
            version=version,
        )
    except TaskNotFoundError:
        _not_found()
    except ReportVersionConflictError:
        raise HTTPException(
            status_code=409,
            detail={"code": "REPORT_VERSION_CONFLICT"},
        ) from None


@router.post("/{task_id}/review", response_model=ReviewResponse)
async def submit_review(
    task_id: str,
    body: ReviewRequest,
    identity: IdentityDependency,
    service: ServiceDependency,
) -> ReviewResponse:
    require_permission(identity, "case.read")
    require_permission(identity, "case.analysis.review")
    try:
        return await service.submit_review(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
            reviewer_id=identity.user_id,
            request=body,
        )
    except TaskNotFoundError:
        _not_found()
    except IdempotencyConflictError:
        _idempotency_conflict()
    except ReportVersionConflictError:
        raise HTTPException(
            status_code=409,
            detail={"code": "REPORT_VERSION_CONFLICT"},
        ) from None
    except ReviewValidationError:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REVIEW"},
        ) from None


@router.post("/{task_id}/casebook", response_model=ArchiveResponse)
async def archive_casebook(
    task_id: str,
    body: ArchiveRequest,
    identity: IdentityDependency,
    service: ServiceDependency,
) -> ArchiveResponse:
    require_permission(identity, "case.read")
    require_permission(identity, "casebook.write")
    try:
        return await service.archive_casebook(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
            review_revision=body.review_revision,
            idempotency_key=body.idempotency_key,
        )
    except TaskNotFoundError:
        _not_found()
    except IdempotencyConflictError:
        _idempotency_conflict()
    except ReviewRevisionConflictError:
        raise HTTPException(
            status_code=409,
            detail={"code": "REVIEW_REVISION_CONFLICT"},
        ) from None
    except ArchiveDisabledError:
        raise HTTPException(
            status_code=403,
            detail={"code": "CASEBOOK_ARCHIVE_DISABLED"},
        ) from None


@router.get("/{task_id}/stream", response_model=None)
async def stream_analysis(
    task_id: str,
    request: Request,
    identity: IdentityDependency,
    service: ServiceDependency,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    require_permission(identity, "case.read")
    cursor = _parse_cursor(last_event_id)
    try:
        initial = await service.stream_batch(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
            after_sequence=cursor,
        )
    except TaskNotFoundError:
        _not_found()
    except EventCursorError:
        _cursor_expired()
    settings = request.app.state.settings
    return StreamingResponse(
        _event_stream(
            request=request,
            identity=identity,
            service=service,
            task_id=task_id,
            cursor=cursor,
            initial=initial,
            poll_seconds=settings.sse_poll_seconds,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
            permission_recheck_seconds=settings.sse_permission_recheck_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{task_id}/retry", response_model=TaskAccepted, status_code=202)
async def retry_analysis(
    task_id: str,
    body: RetryRequest,
    identity: IdentityDependency,
    service: ServiceDependency,
) -> TaskAccepted:
    require_permission(identity, "case.read")
    try:
        return await service.retry(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
            idempotency_key=body.idempotency_key,
        )
    except TaskNotFoundError:
        _not_found()
    except IdempotencyConflictError:
        _idempotency_conflict()
    except RetryNotAllowedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "RETRY_NOT_ALLOWED", "status": str(exc)},
        ) from None


@router.post("/{task_id}/cancel", response_model=TaskSnapshot)
async def cancel_analysis(
    task_id: str,
    identity: IdentityDependency,
    service: ServiceDependency,
) -> TaskSnapshot:
    require_permission(identity, "case.read")
    try:
        return await service.cancel(
            task_id=task_id,
            tenant_id=identity.tenant_id,
            permission_scope_hash=identity.permission_scope_hash,
        )
    except TaskNotFoundError:
        _not_found()


def _parse_cursor(raw: str | None) -> int:
    if raw is None:
        return 0
    if not raw.isascii() or not raw.isdecimal():
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST"})
    return int(raw)


def _cursor_expired() -> NoReturn:
    raise HTTPException(status_code=409, detail={"code": "EVENT_CURSOR_EXPIRED"})


async def _event_stream(
    *,
    request: Request,
    identity: Identity,
    service: TaskService,
    task_id: str,
    cursor: int,
    initial: StreamBatch,
    poll_seconds: float,
    heartbeat_seconds: float,
    permission_recheck_seconds: float,
) -> AsyncIterator[str]:
    batch = initial
    current_identity = identity
    last_heartbeat = monotonic()
    last_permission_check = monotonic()
    while True:
        now = monotonic()
        if now - last_permission_check >= permission_recheck_seconds:
            refreshed = await refresh_identity(request, current_identity)
            if refreshed is None or not refreshed.can("case.read"):
                return
            current_identity = refreshed
            last_permission_check = now
        for event in batch.events:
            cursor = event.sequence
            yield _format_event(task_id, event)
        if batch.terminal and cursor >= batch.latest_sequence:
            return
        if await request.is_disconnected():
            return
        now = monotonic()
        if now - last_heartbeat >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            last_heartbeat = now
        await asyncio.sleep(poll_seconds)
        try:
            batch = await service.stream_batch(
                task_id=task_id,
                tenant_id=current_identity.tenant_id,
                permission_scope_hash=current_identity.permission_scope_hash,
                after_sequence=cursor,
            )
        except (TaskNotFoundError, EventCursorError):
            return


def _format_event(task_id: str, event: StreamEvent) -> str:
    data = {
        "schemaVersion": "1.0.0",
        "taskId": task_id,
        "sequence": event.sequence,
        "occurredAt": event.occurred_at.isoformat().replace("+00:00", "Z"),
        "payload": event.payload,
    }
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.sequence}\nevent: {event.type}\ndata: {serialized}\n\n"


def _idempotency_conflict() -> NoReturn:
    raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"})


def _not_found() -> NoReturn:
    raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"})


def http_error_envelope(status_code: int, detail: object) -> ErrorEnvelope:
    code = "INVALID_REQUEST"
    details: dict[str, object] = {}
    if isinstance(detail, dict):
        raw_code = detail.get("code")
        if isinstance(raw_code, str):
            code = raw_code
        details = {str(key): value for key, value in detail.items() if key != "code"}
    trace_id = str(uuid4())
    return ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=code.replace("_", " ").title(),
            retryable=status_code >= 500,
            trace_id=trace_id,
            details=details,
        )
    )
