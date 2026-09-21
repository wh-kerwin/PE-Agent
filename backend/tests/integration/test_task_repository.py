from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import docker
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from pe_agent.adapters.persistence.models import (
    AnalysisTaskModel,
    Base,
    CaseBookArchiveModel,
    EngineerReviewModel,
    OutboxModel,
    ReportModel,
    TaskEventModel,
)
from pe_agent.adapters.persistence.repositories import (
    NewTask,
    ReportRepository,
    ReviewRepository,
    ReviewValues,
    TaskRepository,
)
from pe_agent.adapters.persistence.session import create_engine, create_session_factory
from pe_agent.api.schemas import ReviewRequest
from pe_agent.application.task_service import (
    EventCursorError,
    IdempotencyConflictError,
    ReportVersionConflictError,
    ReviewRevisionConflictError,
    ReviewValidationError,
    TaskService,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    try:
        client = docker.from_env()
        client.ping()
    except Exception as error:
        pytest.skip(f"Docker engine unavailable: {error}")

    with PostgresContainer("postgres:16-alpine") as postgres:
        database_url = postgres.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+asyncpg"
        )
        engine: AsyncEngine = create_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield create_session_factory(engine)
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True, loop_scope="module")
async def reset_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async with session_factory.begin() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
    yield


async def create_task(session: AsyncSession, *, task_id: str | None = None) -> NewTask:
    now = datetime.now(UTC)
    task = NewTask(
        id=task_id or f"ANA-{uuid4()}",
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=frozenset({"case.read"}),
        authorized_entity_ids=frozenset({"CASE-20260920-001"}),
        case_id="CASE-20260920-001",
        case_version="17",
        permission_scope_hash="scope-hash",
        idempotency_key=str(uuid4()),
        now=now,
    )
    await TaskRepository(session).create_idempotent(task)
    return task


async def test_task_creation_is_idempotent_and_atomic(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    task = NewTask(
        id=f"ANA-{uuid4()}",
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=frozenset({"case.read"}),
        authorized_entity_ids=frozenset({"CASE-20260920-001"}),
        case_id="CASE-20260920-001",
        case_version="17",
        permission_scope_hash="scope-hash",
        idempotency_key=str(uuid4()),
        now=datetime.now(UTC),
    )
    async with session_factory.begin() as session:
        created, reused = await TaskRepository(session).create_idempotent(task)
        assert created.id == task.id
        assert reused is False

    async with session_factory.begin() as session:
        replay = NewTask(**{**task.__dict__, "id": f"ANA-{uuid4()}"})
        existing, reused = await TaskRepository(session).create_idempotent(replay)
        assert existing.id == task.id
        assert reused is True
        assert await session.scalar(
            select(func.count()).select_from(OutboxModel).where(
                OutboxModel.aggregate_id == task.id
            )
        ) == 1
        events = list(
            await session.scalars(
                select(TaskEventModel).where(TaskEventModel.task_id == task.id)
            )
        )
        assert [(event.sequence, event.type) for event in events] == [
            (1, "analysis_started")
        ]


async def test_event_sequence_is_unique(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        task = await create_task(session)
        repository = TaskRepository(session)
        await repository.append_event(task.id, "phase_changed", {}, task.now)
        session.add(
            TaskEventModel(
                task_id=task.id,
                sequence=2,
                type="phase_changed",
                payload_redacted={},
                occurred_at=task.now,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_reports_are_versioned_and_immutable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        task = await create_task(session)
        repository = ReportRepository(session)
        first = await repository.add(task.id, 1, {"synthetic": True}, "1.0.0", task.now)
        assert first.report_hash
        session.add(
            ReportModel(
                task_id=task.id,
                version=1,
                schema_version="1.0.0",
                report_json={"synthetic": True, "changed": True},
                report_hash="different",
                created_at=task.now,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_review_revisions_do_not_change_report(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        task = await create_task(session)
        await ReportRepository(session).add(
            task.id, 1, {"synthetic": True}, "1.0.0", task.now
        )
        reviews = ReviewRepository(session)
        first = await reviews.add_revision(
            task_id=task.id,
            values=ReviewValues(
                report_version=1,
                status="INCONCLUSIVE",
                helpful=None,
                reviewer_id="synthetic-reviewer",
                confirmed_hypothesis_id=None,
                root_cause=None,
                comment=None,
            ),
            idempotency_key=str(uuid4()),
            created_at=task.now,
        )
        second = await reviews.add_revision(
            task_id=task.id,
            values=ReviewValues(
                report_version=1,
                status="CORRECTED",
                helpful=True,
                reviewer_id="synthetic-reviewer",
                confirmed_hypothesis_id=None,
                root_cause="Synthetic calibration drift",
                comment=None,
            ),
            idempotency_key=str(uuid4()),
            created_at=task.now + timedelta(seconds=1),
        )
        assert first.revision == 1
        assert second.revision == 2
        report = await ReportRepository(session).latest(task.id)
        assert report is not None
        assert report.report_json == {"synthetic": True}


async def test_finalize_rejects_expired_lease_without_orphan_report(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        task = await create_task(session)
        lease = await TaskRepository(session).claim(now, timedelta(seconds=1))
        assert lease is not None

    async with session_factory.begin() as session:
        repository = TaskRepository(session)
        assert not await repository.finalize(
            lease,
            expected_statuses={"CREATED"},
            status="COMPLETED",
            phase="compose_and_validate_report",
            now=now + timedelta(seconds=2),
            report={"synthetic": True},
            report_version=1,
            schema_version="1.0.0",
        )

    async with session_factory.begin() as session:
        assert await ReportRepository(session).latest(task.id) is None
        assert await TaskRepository(session).latest_event_sequence(task.id) == 1


async def test_stale_fence_cannot_finalize_after_reclaim(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        task = await create_task(session)
        stale = await TaskRepository(session).claim(now, timedelta(seconds=1))
        assert stale is not None

    async with session_factory.begin() as session:
        current = await TaskRepository(session).claim(
            now + timedelta(seconds=2), timedelta(seconds=10)
        )
        assert current is not None
        assert current.fence > stale.fence

    async with session_factory.begin() as session:
        assert not await TaskRepository(session).finalize(
            stale,
            expected_statuses={"CREATED"},
            status="COMPLETED",
            phase="compose_and_validate_report",
            now=now + timedelta(seconds=3),
            report={"synthetic": True},
            report_version=1,
            schema_version="1.0.0",
        )
        assert await ReportRepository(session).latest(task.id) is None


async def test_cancel_wins_against_worker_finalize(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        task = await create_task(session)
        lease = await TaskRepository(session).claim(now, timedelta(seconds=10))
        assert lease is not None

    async with session_factory.begin() as session:
        cancelled = await TaskRepository(session).cancel_visible(
            task.id,
            task.tenant_id,
            task.permission_scope_hash,
            now + timedelta(seconds=1),
        )
        assert cancelled is not None
        assert cancelled.status == "CANCELLED"

    async with session_factory.begin() as session:
        assert not await TaskRepository(session).finalize(
            lease,
            expected_statuses={"CREATED"},
            status="COMPLETED",
            phase="compose_and_validate_report",
            now=now + timedelta(seconds=2),
            report={"synthetic": True},
            report_version=1,
            schema_version="1.0.0",
        )
        assert await ReportRepository(session).latest(task.id) is None


async def test_finalize_is_atomic_when_report_insert_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        task = await create_task(session)
        await ReportRepository(session).add(
            task.id, 1, {"synthetic": True}, "1.0.0", now
        )
        lease = await TaskRepository(session).claim(now, timedelta(seconds=10))
        assert lease is not None

    with pytest.raises(IntegrityError):
        async with session_factory.begin() as session:
            await TaskRepository(session).finalize(
                lease,
                expected_statuses={"CREATED"},
                status="COMPLETED",
                phase="compose_and_validate_report",
                now=now + timedelta(seconds=1),
                report={"synthetic": True, "duplicate": True},
                report_version=1,
                schema_version="1.0.0",
            )

    async with session_factory.begin() as session:
        persisted = await session.get(AnalysisTaskModel, task.id)
        assert persisted is not None
        assert persisted.status == "CREATED"
        assert persisted.lease_token == lease.token
        assert persisted.lease_deadline is not None
        assert await TaskRepository(session).latest_event_sequence(task.id) == 1
        report_count = await session.scalar(
            select(func.count()).select_from(ReportModel).where(
                ReportModel.task_id == task.id
            )
        )
        assert report_count == 1


async def test_finalize_clears_lease_and_appends_report_before_terminal_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        task = await create_task(session)
        lease = await TaskRepository(session).claim(now, timedelta(seconds=10))
        assert lease is not None
        assert await TaskRepository(session).finalize(
            lease,
            expected_statuses={"CREATED"},
            status="PARTIAL_RESULT",
            phase="compose_and_validate_report",
            now=now + timedelta(seconds=1),
            report={"synthetic": True},
            report_version=1,
            schema_version="1.0.0",
        )

    async with session_factory.begin() as session:
        persisted = await session.get(AnalysisTaskModel, task.id)
        assert persisted is not None
        assert persisted.status == "PARTIAL_RESULT"
        assert persisted.lease_token is None
        assert persisted.lease_deadline is None
        events = list(
            await session.scalars(
                select(TaskEventModel)
                .where(TaskEventModel.task_id == task.id)
                .order_by(TaskEventModel.sequence)
            )
        )
        assert [(event.sequence, event.type) for event in events] == [
            (1, "analysis_started"),
            (2, "report_generated"),
            (3, "analysis_partial"),
        ]


async def test_expired_lease_reclaim_and_terminal_cas(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with session_factory.begin() as session:
        task = await create_task(session)
        repository = TaskRepository(session)
        first = await repository.claim(now, timedelta(seconds=5))
        assert first is not None

    async with session_factory.begin() as session:
        repository = TaskRepository(session)
        reclaimed = await repository.claim(now + timedelta(seconds=6), timedelta(seconds=5))
        assert reclaimed is not None
        assert reclaimed.task_id == task.id
        assert reclaimed.fence > first.fence
        assert await repository.transition(
            reclaimed,
            {"CREATED"},
            "COMPLETED",
            "compose_and_validate_report",
            100,
            now + timedelta(seconds=7),
            "analysis_completed",
        )
        assert not await repository.transition(
            first,
            {"CREATED"},
            "FAILED",
            None,
            100,
            now + timedelta(seconds=8),
            "analysis_failed",
        )


async def seed_report(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    task_id: str,
) -> NewTask:
    async with session_factory.begin() as session:
        task = await create_task(session, task_id=task_id)
        await ReportRepository(session).add(
            task.id,
            1,
            {
                "synthetic": True,
                "hypotheses": [
                    {"hypothesisId": "HYP-SYN-1", "title": "Synthetic hypothesis"}
                ],
            },
            "1.0.0",
            task.now,
        )
    return task


def review_request(
    *,
    idempotency_key: str,
    status: str = "INCONCLUSIVE",
    report_version: int = 1,
    hypothesis_id: str | None = None,
    comment: str | None = None,
) -> ReviewRequest:
    return ReviewRequest(
        report_version=report_version,
        review_status=status,
        confirmed_hypothesis_id=hypothesis_id,
        comment=comment,
        idempotency_key=idempotency_key,
    )


async def test_review_service_enforces_version_validation_and_idempotency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    task = await seed_report(session_factory, task_id="ANA-REVIEW-VALIDATION")
    service = TaskService(session_factory, clock=lambda: task.now)
    request = review_request(idempotency_key="review-idem")
    arguments = {
        "task_id": task.id,
        "tenant_id": task.tenant_id,
        "permission_scope_hash": task.permission_scope_hash,
        "reviewer_id": "synthetic-reviewer",
    }

    first = await service.submit_review(request=request, **arguments)
    replay = await service.submit_review(request=request, **arguments)

    assert first.review_revision == 1
    assert replay == first
    with pytest.raises(IdempotencyConflictError):
        await service.submit_review(
            request=review_request(
                idempotency_key="review-idem", comment="Different payload"
            ),
            **arguments,
        )
    with pytest.raises(ReportVersionConflictError):
        await service.submit_review(
            request=review_request(
                idempotency_key="wrong-version", report_version=2
            ),
            **arguments,
        )
    with pytest.raises(ReviewValidationError):
        await service.submit_review(
            request=review_request(
                idempotency_key="unknown-hypothesis",
                status="CONFIRMED",
                hypothesis_id="HYP-NOT-PRESENT",
            ),
            **arguments,
        )


async def test_concurrent_reviews_allocate_distinct_revisions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    task = await seed_report(session_factory, task_id="ANA-REVIEW-CONCURRENT")
    service = TaskService(session_factory, clock=lambda: task.now)

    responses = await asyncio.gather(
        *(
            service.submit_review(
                task_id=task.id,
                tenant_id=task.tenant_id,
                permission_scope_hash=task.permission_scope_hash,
                reviewer_id=f"synthetic-reviewer-{index}",
                request=review_request(idempotency_key=f"review-{index}"),
            )
            for index in range(2)
        )
    )

    assert {response.review_revision for response in responses} == {1, 2}
    async with session_factory.begin() as session:
        revisions = list(
            await session.scalars(
                select(EngineerReviewModel.revision)
                .where(EngineerReviewModel.task_id == task.id)
                .order_by(EngineerReviewModel.revision)
            )
        )
    assert revisions == [1, 2]


async def test_review_idempotency_key_is_scoped_to_task(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_task = await seed_report(session_factory, task_id="ANA-REVIEW-SCOPE-1")
    second_task = await seed_report(session_factory, task_id="ANA-REVIEW-SCOPE-2")
    service = TaskService(session_factory, clock=lambda: first_task.now)
    request = review_request(idempotency_key="shared-review-key")

    responses = []
    for task in (first_task, second_task):
        responses.append(
            await service.submit_review(
                task_id=task.id,
                tenant_id=task.tenant_id,
                permission_scope_hash=task.permission_scope_hash,
                reviewer_id="synthetic-reviewer",
                request=request,
            )
        )

    assert [response.task_id for response in responses] == [
        first_task.id,
        second_task.id,
    ]
    assert [response.review_revision for response in responses] == [1, 1]


async def test_archive_requires_existing_revision_and_is_task_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    task = await seed_report(session_factory, task_id="ANA-ARCHIVE")
    service = TaskService(
        session_factory,
        clock=lambda: task.now,
        archive_id_factory=lambda: "CB-SYN-FIXED",
        archive_enabled=True,
    )
    arguments = {
        "task_id": task.id,
        "tenant_id": task.tenant_id,
        "permission_scope_hash": task.permission_scope_hash,
        "reviewer_id": "synthetic-reviewer",
    }
    await service.submit_review(
        request=review_request(idempotency_key="review-1"), **arguments
    )
    await service.submit_review(
        request=review_request(idempotency_key="review-2", comment="Revision 2"),
        **arguments,
    )

    with pytest.raises(ReviewRevisionConflictError):
        await service.archive_casebook(
            task_id=task.id,
            tenant_id=task.tenant_id,
            permission_scope_hash=task.permission_scope_hash,
            review_revision=3,
            idempotency_key="archive-missing",
        )

    archived = await service.archive_casebook(
        task_id=task.id,
        tenant_id=task.tenant_id,
        permission_scope_hash=task.permission_scope_hash,
        review_revision=1,
        idempotency_key="archive-idem",
    )
    replay = await service.archive_casebook(
        task_id=task.id,
        tenant_id=task.tenant_id,
        permission_scope_hash=task.permission_scope_hash,
        review_revision=1,
        idempotency_key="archive-idem",
    )

    assert replay == archived
    assert archived.archive_id == "CB-SYN-FIXED"
    with pytest.raises(IdempotencyConflictError):
        await service.archive_casebook(
            task_id=task.id,
            tenant_id=task.tenant_id,
            permission_scope_hash=task.permission_scope_hash,
            review_revision=2,
            idempotency_key="archive-idem",
        )
    async with session_factory.begin() as session:
        archive_count = await session.scalar(
            select(func.count()).select_from(CaseBookArchiveModel).where(
                CaseBookArchiveModel.task_id == task.id
            )
        )
    assert archive_count == 1


async def test_stream_batch_rejects_ahead_and_expired_cursors(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        task = await create_task(session, task_id="ANA-STREAM-CURSOR")
        repository = TaskRepository(session)
        await repository.append_event(task.id, "phase_changed", {}, task.now)
        await repository.append_event(task.id, "phase_changed", {}, task.now)
    service = TaskService(session_factory, sse_replay_limit=2)
    arguments = {
        "task_id": task.id,
        "tenant_id": task.tenant_id,
        "permission_scope_hash": task.permission_scope_hash,
    }

    with pytest.raises(EventCursorError):
        await service.stream_batch(after_sequence=4, **arguments)
    with pytest.raises(EventCursorError):
        await service.stream_batch(after_sequence=0, **arguments)

    batch = await service.stream_batch(after_sequence=1, **arguments)
    assert [event.sequence for event in batch.events] == [2, 3]
    assert batch.latest_sequence == 3
