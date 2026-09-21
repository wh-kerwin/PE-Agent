from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pe_agent.adapters.persistence.models import (
    AnalysisTaskModel,
    EngineerReviewModel,
    TaskEventModel,
)
from pe_agent.adapters.persistence.repositories import (
    ArchiveValues,
    CaseBookArchiveRepository,
    NewTask,
    ReportRepository,
    ReviewRepository,
    ReviewValues,
    TaskRepository,
)
from pe_agent.api.schemas import (
    ArchiveResponse,
    ReviewRequest,
    ReviewResponse,
    TaskAccepted,
    TaskSnapshot,
)
from pe_agent.domain import EngineerReview, ReviewStatus

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]
RETRYABLE_STATUSES = {"FAILED", "TIMEOUT", "PARTIAL_RESULT"}
TERMINAL_STATUSES = {"COMPLETED", "PARTIAL_RESULT", "FAILED", "TIMEOUT", "CANCELLED"}


@dataclass(frozen=True)
class StreamEvent:
    sequence: int
    type: str
    payload: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class StreamBatch:
    events: tuple[StreamEvent, ...]
    terminal: bool
    latest_sequence: int


class TaskNotFoundError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class ReportVersionConflictError(ValueError):
    pass


class RetryNotAllowedError(ValueError):
    pass


class ReviewValidationError(ValueError):
    pass


class ReviewRevisionConflictError(ValueError):
    pass


class ArchiveDisabledError(RuntimeError):
    pass


class EventCursorError(ValueError):
    pass


class TaskService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock | None = None,
        id_factory: IdFactory | None = None,
        archive_id_factory: IdFactory | None = None,
        archive_enabled: bool = False,
        sse_replay_limit: int = 500,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: f"ANA-{uuid4()}")
        self._archive_id_factory = archive_id_factory or (lambda: f"CB-SYN-{uuid4()}")
        self._archive_enabled = archive_enabled
        self._sse_replay_limit = sse_replay_limit

    async def create_or_resume(
        self,
        *,
        tenant_id: str,
        user_id: str,
        permissions: frozenset[str],
        authorized_entity_ids: frozenset[str],
        permission_scope_hash: str,
        case_id: str,
        case_version: str,
        idempotency_key: str,
    ) -> TaskAccepted:
        async with self._session_factory.begin() as session:
            repository = TaskRepository(session)
            await repository.lock_idempotency_scope(
                tenant_id,
                permission_scope_hash,
                idempotency_key,
            )
            replay = await repository.find_by_idempotency_key(
                tenant_id,
                permission_scope_hash,
                idempotency_key,
            )
            if replay is not None:
                if (
                    replay.case_id != case_id
                    or replay.case_version != case_version
                    or replay.supersedes_task_id is not None
                ):
                    raise IdempotencyConflictError(idempotency_key)
                return self._accepted(replay, reused=True)
            await repository.lock_case_scope(
                tenant_id,
                case_id,
                case_version,
                permission_scope_hash,
            )
            running = await repository.running_for_case(
                tenant_id,
                case_id,
                case_version,
                permission_scope_hash,
            )
            if running is not None:
                return self._accepted(running, reused=True)
            task, reused = await repository.create_idempotent(
                NewTask(
                    id=self._id_factory(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    permissions=permissions,
                    authorized_entity_ids=authorized_entity_ids,
                    case_id=case_id,
                    case_version=case_version,
                    permission_scope_hash=permission_scope_hash,
                    idempotency_key=idempotency_key,
                    now=self._now(),
                )
            )
            return self._accepted(task, reused=reused)

    async def get_snapshot(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
    ) -> TaskSnapshot:
        async with self._session_factory.begin() as session:
            task = await TaskRepository(session).get_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
            )
            if task is None:
                raise TaskNotFoundError(task_id)
            return await self._snapshot(session, task)

    async def get_report(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        version: int | None,
    ) -> dict[str, Any]:
        async with self._session_factory.begin() as session:
            task = await TaskRepository(session).get_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
            )
            if task is None:
                raise TaskNotFoundError(task_id)
            reports = ReportRepository(session)
            report = (
                await reports.latest(task_id)
                if version is None
                else await reports.get_version(task_id, version)
            )
            if report is None:
                raise ReportVersionConflictError(version)
            return report.report_json

    async def get_latest_snapshot(
        self,
        *,
        case_id: str,
        tenant_id: str,
        permission_scope_hash: str,
    ) -> TaskSnapshot:
        async with self._session_factory.begin() as session:
            task = await TaskRepository(session).latest_for_case(
                tenant_id,
                case_id,
                permission_scope_hash,
            )
            if task is None:
                raise TaskNotFoundError(case_id)
            return await self._snapshot(session, task)

    async def retry(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        idempotency_key: str,
    ) -> TaskAccepted:
        async with self._session_factory.begin() as session:
            repository = TaskRepository(session)
            await repository.lock_idempotency_scope(
                tenant_id,
                permission_scope_hash,
                idempotency_key,
            )
            replay = await repository.find_by_idempotency_key(
                tenant_id,
                permission_scope_hash,
                idempotency_key,
            )
            if replay is not None:
                if replay.supersedes_task_id != task_id:
                    raise IdempotencyConflictError(idempotency_key)
                return self._accepted(replay, reused=True)
            original = await repository.get_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
                for_update=True,
            )
            if original is None:
                raise TaskNotFoundError(task_id)
            if original.status not in RETRYABLE_STATUSES:
                raise RetryNotAllowedError(original.status)
            successor = await repository.latest_superseding(
                task_id,
                tenant_id,
                permission_scope_hash,
            )
            if successor is not None:
                return self._accepted(successor, reused=True)
            successor, reused = await repository.create_idempotent(
                NewTask(
                    id=self._id_factory(),
                    tenant_id=tenant_id,
                    user_id=original.user_id,
                    permissions=frozenset(original.permissions),
                    authorized_entity_ids=frozenset(original.authorized_entity_ids),
                    case_id=original.case_id,
                    case_version=original.case_version,
                    permission_scope_hash=permission_scope_hash,
                    idempotency_key=idempotency_key,
                    now=self._now(),
                    supersedes_task_id=original.id,
                )
            )
            return self._accepted(successor, reused=reused)

    async def cancel(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
    ) -> TaskSnapshot:
        async with self._session_factory.begin() as session:
            task = await TaskRepository(session).cancel_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
                self._now(),
            )
            if task is None:
                raise TaskNotFoundError(task_id)
            return await self._snapshot(session, task)

    async def submit_review(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        reviewer_id: str,
        request: ReviewRequest,
    ) -> ReviewResponse:
        async with self._session_factory.begin() as session:
            tasks = TaskRepository(session)
            task = await tasks.get_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
                for_update=True,
            )
            if task is None:
                raise TaskNotFoundError(task_id)
            reviews = ReviewRepository(session)
            existing = await reviews.find_by_idempotency_key(
                task_id,
                request.idempotency_key,
            )
            if existing is not None:
                if not self._review_matches(existing, request, reviewer_id):
                    raise IdempotencyConflictError(request.idempotency_key)
                return self._review_response(existing)
            report = await ReportRepository(session).latest(task_id)
            if report is None or report.version != request.report_version:
                raise ReportVersionConflictError(request.report_version)
            self._validate_review(request, report.report_json)
            review = await reviews.add_revision(
                task_id=task_id,
                values=ReviewValues(
                    report_version=request.report_version,
                    status=request.review_status,
                    helpful=request.helpful,
                    reviewer_id=reviewer_id,
                    confirmed_hypothesis_id=request.confirmed_hypothesis_id,
                    root_cause=request.actual_root_cause,
                    comment=request.comment,
                ),
                idempotency_key=request.idempotency_key,
                created_at=self._now(),
            )
            return self._review_response(review)

    async def archive_casebook(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        review_revision: int,
        idempotency_key: str,
    ) -> ArchiveResponse:
        async with self._session_factory.begin() as session:
            task = await TaskRepository(session).get_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
                for_update=True,
            )
            if task is None:
                raise TaskNotFoundError(task_id)
            if not self._archive_enabled:
                raise ArchiveDisabledError(task_id)
            reviews = ReviewRepository(session)
            review = await reviews.get_revision(task_id, review_revision)
            if review is None:
                raise ReviewRevisionConflictError(review_revision)
            archives = CaseBookArchiveRepository(session)
            existing = await archives.find_by_idempotency_key(task_id, idempotency_key)
            if existing is not None:
                if existing.review_id != review.id:
                    raise IdempotencyConflictError(idempotency_key)
                return ArchiveResponse(
                    archive_id=existing.external_id or existing.id,
                    status=cast(
                        Literal["PENDING", "ARCHIVED", "FAILED"], existing.status
                    ),
                    review_revision=review_revision,
                    message="Synthetic Case Book archive; no customer system was called.",
                )
            archive_id = self._archive_id_factory()
            archive = await archives.add(
                archive_id=archive_id,
                task_id=task_id,
                values=ArchiveValues(
                    review_id=review.id,
                    status="ARCHIVED",
                    external_id=archive_id,
                    error_code=None,
                ),
                idempotency_key=idempotency_key,
                now=self._now(),
            )
            return ArchiveResponse(
                archive_id=archive.external_id or archive.id,
                status="ARCHIVED",
                review_revision=review_revision,
                message="Synthetic Case Book archive; no customer system was called.",
            )

    async def stream_batch(
        self,
        *,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        after_sequence: int,
    ) -> StreamBatch:
        async with self._session_factory.begin() as session:
            task = await TaskRepository(session).get_visible(
                task_id,
                tenant_id,
                permission_scope_hash,
            )
            if task is None:
                raise TaskNotFoundError(task_id)
            repository = TaskRepository(session)
            latest_sequence = await repository.latest_event_sequence(task_id)
            if after_sequence > latest_sequence or (
                latest_sequence - after_sequence > self._sse_replay_limit
            ):
                raise EventCursorError(after_sequence)
            models = await repository.events_after(task_id, after_sequence)
            events = tuple(self._stream_event(model) for model in models)
            terminal = task.status in TERMINAL_STATUSES
            return StreamBatch(
                events=events,
                terminal=terminal,
                latest_sequence=latest_sequence,
            )

    async def _snapshot(
        self,
        session: AsyncSession,
        task: AnalysisTaskModel,
    ) -> TaskSnapshot:
        tasks = TaskRepository(session)
        report = await ReportRepository(session).latest(task.id)
        review = await ReviewRepository(session).latest(task.id)
        return TaskSnapshot(
            task_id=task.id,
            case_id=task.case_id,
            case_version=task.case_version,
            status=task.status,
            phase=task.phase,
            progress=task.progress,
            review_status=review.status if review is not None else "NOT_REVIEWED",
            warnings=[],
            latest_event_id=str(await tasks.latest_event_sequence(task.id)),
            report_version=report.version if report is not None else None,
            report_url=(
                f"/api/ai/case-analysis/{task.id}/report?version={report.version}"
                if report is not None
                else None
            ),
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
            supersedes_task_id=task.supersedes_task_id,
            versions={
                "agent": task.agent_version,
                "model": task.model_version,
                "prompt": task.prompt_version,
                "schema": task.schema_version,
            },
        )

    @staticmethod
    def _validate_review(request: ReviewRequest, report: dict[str, Any]) -> None:
        try:
            EngineerReview(
                task_id="validation",
                report_version=request.report_version,
                revision=1,
                status=ReviewStatus(request.review_status),
                helpful=request.helpful,
                confirmed_hypothesis_id=request.confirmed_hypothesis_id,
                actual_root_cause=request.actual_root_cause,
                comment=request.comment,
                reviewed_at=datetime.now(UTC),
            )
        except ValueError as error:
            raise ReviewValidationError from error
        if request.confirmed_hypothesis_id is not None:
            hypotheses = report.get("hypotheses")
            hypothesis_items = hypotheses if isinstance(hypotheses, list) else []
            known_ids = {
                item.get("hypothesisId")
                for item in hypothesis_items
                if isinstance(item, dict)
            }
            if request.confirmed_hypothesis_id not in known_ids:
                raise ReviewValidationError("unknown hypothesis")

    @staticmethod
    def _review_matches(
        review: EngineerReviewModel,
        request: ReviewRequest,
        reviewer_id: str,
    ) -> bool:
        return bool(
            review.report_version == request.report_version
            and review.status == request.review_status
            and review.helpful == request.helpful
            and review.confirmed_hypothesis_id == request.confirmed_hypothesis_id
            and review.root_cause == request.actual_root_cause
            and review.comment == request.comment
            and review.reviewer_id == reviewer_id
        )

    @staticmethod
    def _review_response(review: Any) -> ReviewResponse:
        return ReviewResponse(
            task_id=review.task_id,
            report_version=review.report_version,
            review_status=review.status,
            helpful=review.helpful,
            confirmed_hypothesis_id=review.confirmed_hypothesis_id,
            actual_root_cause=review.root_cause,
            comment=review.comment,
            idempotency_key=review.idempotency_key,
            review_revision=review.revision,
            created_at=review.created_at,
        )

    @staticmethod
    def _stream_event(event: TaskEventModel) -> StreamEvent:
        return StreamEvent(
            sequence=event.sequence,
            type=event.type,
            payload=event.payload_redacted,
            occurred_at=event.occurred_at,
        )

    def _accepted(self, task: AnalysisTaskModel, *, reused: bool) -> TaskAccepted:
        return TaskAccepted(
            task_id=task.id,
            case_id=task.case_id,
            case_version=task.case_version,
            status=task.status,
            reused=reused,
            stream_url=f"/api/ai/case-analysis/{task.id}/stream",
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return an aware timestamp")
        return now
