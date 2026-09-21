from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pe_agent.adapters.persistence.models import (
    AnalysisTaskModel,
    CaseBookArchiveModel,
    EngineerReviewModel,
    OutboxModel,
    ReportModel,
    TaskEventModel,
)

TERMINAL_STATUSES = {"COMPLETED", "PARTIAL_RESULT", "FAILED", "TIMEOUT", "CANCELLED"}
ACTIVE_STATUSES = {
    "CREATED",
    "CONTEXT_LOADING",
    "INVESTIGATING",
    "ANALYZING",
    "GENERATING_REPORT",
}


@dataclass(frozen=True)
class NewTask:
    id: str
    tenant_id: str
    user_id: str
    permissions: frozenset[str]
    authorized_entity_ids: frozenset[str]
    case_id: str
    case_version: str
    permission_scope_hash: str
    idempotency_key: str
    now: datetime
    agent_version: str = "yield-drop-v1"
    model_version: str = "jev-1.13.0"
    prompt_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    supersedes_task_id: str | None = None


@dataclass(frozen=True)
class Lease:
    task_id: str
    token: str
    fence: int
    deadline: datetime


@dataclass(frozen=True)
class ReviewValues:
    report_version: int
    status: str
    helpful: bool | None
    reviewer_id: str
    confirmed_hypothesis_id: str | None
    root_cause: str | None
    comment: str | None


@dataclass(frozen=True)
class ArchiveValues:
    review_id: str
    status: str
    external_id: str | None
    error_code: str | None


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_idempotency_scope(
        self,
        tenant_id: str,
        permission_scope_hash: str,
        idempotency_key: str,
    ) -> None:
        lock_key = ":".join((tenant_id, permission_scope_hash, idempotency_key))
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )

    async def lock_case_scope(
        self,
        tenant_id: str,
        case_id: str,
        case_version: str,
        permission_scope_hash: str,
    ) -> None:
        lock_key = ":".join(
            (tenant_id, case_id, case_version, permission_scope_hash)
        )
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )

    async def find_by_idempotency_key(
        self,
        tenant_id: str,
        permission_scope_hash: str,
        idempotency_key: str,
    ) -> AnalysisTaskModel | None:
        return cast(
            AnalysisTaskModel | None,
            await self._session.scalar(
                select(AnalysisTaskModel).where(
                    AnalysisTaskModel.tenant_id == tenant_id,
                    AnalysisTaskModel.permission_scope_hash == permission_scope_hash,
                    AnalysisTaskModel.idempotency_key == idempotency_key,
                )
            ),
        )

    async def create_idempotent(self, new_task: NewTask) -> tuple[AnalysisTaskModel, bool]:
        values = {
            "id": new_task.id,
            "tenant_id": new_task.tenant_id,
            "user_id": new_task.user_id,
            "permissions": sorted(new_task.permissions),
            "authorized_entity_ids": sorted(new_task.authorized_entity_ids),
            "case_id": new_task.case_id,
            "case_version": new_task.case_version,
            "permission_scope_hash": new_task.permission_scope_hash,
            "idempotency_key": new_task.idempotency_key,
            "status": "CREATED",
            "phase": None,
            "progress": 0,
            "agent_version": new_task.agent_version,
            "model_version": new_task.model_version,
            "prompt_version": new_task.prompt_version,
            "schema_version": new_task.schema_version,
            "supersedes_task_id": new_task.supersedes_task_id,
            "created_at": new_task.now,
            "updated_at": new_task.now,
        }
        statement = (
            insert(AnalysisTaskModel)
            .values(**values)
            .on_conflict_do_nothing(
                constraint="uq_task_idempotency_scope",
            )
            .returning(AnalysisTaskModel.id)
        )
        inserted_id = (await self._session.execute(statement)).scalar_one_or_none()
        if inserted_id is not None:
            self._session.add(
                OutboxModel(
                    id=str(uuid4()),
                    aggregate_id=new_task.id,
                    type="analysis_requested",
                    payload={"taskId": new_task.id},
                    created_at=new_task.now,
                )
            )
            await self.append_event(
                new_task.id,
                "analysis_started",
                {"caseId": new_task.case_id},
                new_task.now,
            )
            task = await self.get(new_task.id)
            return task, False

        existing = await self._session.scalar(
            select(AnalysisTaskModel).where(
                AnalysisTaskModel.tenant_id == new_task.tenant_id,
                AnalysisTaskModel.permission_scope_hash == new_task.permission_scope_hash,
                AnalysisTaskModel.idempotency_key == new_task.idempotency_key,
            )
        )
        if existing is None:
            raise RuntimeError("idempotent task lookup failed")
        return existing, True

    async def get(self, task_id: str, *, for_update: bool = False) -> AnalysisTaskModel:
        statement = select(AnalysisTaskModel).where(AnalysisTaskModel.id == task_id)
        if for_update:
            statement = statement.with_for_update()
        task = await self._session.scalar(statement)
        if task is None:
            raise LookupError(task_id)
        return task

    async def get_visible(
        self,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        *,
        for_update: bool = False,
    ) -> AnalysisTaskModel | None:
        statement = select(AnalysisTaskModel).where(
            AnalysisTaskModel.id == task_id,
            AnalysisTaskModel.tenant_id == tenant_id,
            AnalysisTaskModel.permission_scope_hash == permission_scope_hash,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(AnalysisTaskModel | None, await self._session.scalar(statement))

    async def latest_for_case(
        self,
        tenant_id: str,
        case_id: str,
        permission_scope_hash: str,
    ) -> AnalysisTaskModel | None:
        return cast(
            AnalysisTaskModel | None,
            await self._session.scalar(
                select(AnalysisTaskModel)
                .where(
                    AnalysisTaskModel.tenant_id == tenant_id,
                    AnalysisTaskModel.case_id == case_id,
                    AnalysisTaskModel.permission_scope_hash == permission_scope_hash,
                )
                .order_by(AnalysisTaskModel.created_at.desc())
                .limit(1)
            ),
        )

    async def latest_superseding(
        self,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
    ) -> AnalysisTaskModel | None:
        return cast(
            AnalysisTaskModel | None,
            await self._session.scalar(
                select(AnalysisTaskModel)
                .where(
                    AnalysisTaskModel.supersedes_task_id == task_id,
                    AnalysisTaskModel.tenant_id == tenant_id,
                    AnalysisTaskModel.permission_scope_hash == permission_scope_hash,
                )
                .order_by(AnalysisTaskModel.created_at.desc())
                .limit(1)
            ),
        )

    async def running_for_case(
        self,
        tenant_id: str,
        case_id: str,
        case_version: str,
        permission_scope_hash: str,
    ) -> AnalysisTaskModel | None:
        return cast(
            AnalysisTaskModel | None,
            await self._session.scalar(
                select(AnalysisTaskModel)
                .where(
                    AnalysisTaskModel.tenant_id == tenant_id,
                    AnalysisTaskModel.case_id == case_id,
                    AnalysisTaskModel.case_version == case_version,
                    AnalysisTaskModel.permission_scope_hash == permission_scope_hash,
                    AnalysisTaskModel.status.in_(ACTIVE_STATUSES),
                )
                .order_by(AnalysisTaskModel.created_at.desc())
                .limit(1)
            ),
        )

    async def append_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> TaskEventModel:
        await self.get(task_id, for_update=True)
        next_sequence = (
            await self._session.scalar(
                select(func.coalesce(func.max(TaskEventModel.sequence), 0) + 1).where(
                    TaskEventModel.task_id == task_id
                )
            )
        )
        event = TaskEventModel(
            task_id=task_id,
            sequence=int(next_sequence or 1),
            type=event_type,
            payload_redacted=payload,
            occurred_at=occurred_at,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def latest_event_sequence(self, task_id: str) -> int:
        sequence = await self._session.scalar(
            select(func.coalesce(func.max(TaskEventModel.sequence), 0)).where(
                TaskEventModel.task_id == task_id
            )
        )
        return int(sequence or 0)

    async def cancel_visible(
        self,
        task_id: str,
        tenant_id: str,
        permission_scope_hash: str,
        now: datetime,
    ) -> AnalysisTaskModel | None:
        task = await self.get_visible(
            task_id,
            tenant_id,
            permission_scope_hash,
            for_update=True,
        )
        if task is None:
            return None
        if task.status in TERMINAL_STATUSES:
            return task
        result = await self._session.execute(
            update(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.id == task_id,
                ~AnalysisTaskModel.status.in_(TERMINAL_STATUSES),
            )
            .values(
                status="CANCELLED",
                phase=None,
                updated_at=now,
                completed_at=now,
                lease_token=None,
                lease_deadline=None,
            )
        )
        if getattr(result, "rowcount", 0) == 1:
            await self.append_event(task_id, "analysis_cancelled", {}, now)
        return await self.get(task_id)

    async def events_after(self, task_id: str, sequence: int) -> list[TaskEventModel]:
        result = await self._session.scalars(
            select(TaskEventModel)
            .where(TaskEventModel.task_id == task_id, TaskEventModel.sequence > sequence)
            .order_by(TaskEventModel.sequence)
        )
        return list(result)

    async def claim(self, now: datetime, lease_duration: timedelta) -> Lease | None:
        statement = (
            select(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.status.in_(ACTIVE_STATUSES),
                (AnalysisTaskModel.lease_deadline.is_(None))
                | (AnalysisTaskModel.lease_deadline < now),
            )
            .order_by(AnalysisTaskModel.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        task = await self._session.scalar(statement)
        if task is None:
            return None
        task.fence += 1
        task.lease_token = str(uuid4())
        task.lease_deadline = now + lease_duration
        task.updated_at = now
        await self._session.flush()
        return Lease(task.id, task.lease_token, task.fence, task.lease_deadline)

    async def transition(
        self,
        lease: Lease,
        expected_statuses: set[str],
        status: str,
        phase: str | None,
        progress: int,
        now: datetime,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        completed_at = now if status in TERMINAL_STATUSES else None
        terminal_values: dict[str, Any] = {}
        if status in TERMINAL_STATUSES:
            terminal_values = {"lease_token": None, "lease_deadline": None}
        result = await self._session.execute(
            update(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.id == lease.task_id,
                AnalysisTaskModel.fence == lease.fence,
                AnalysisTaskModel.lease_token == lease.token,
                AnalysisTaskModel.lease_deadline >= now,
                AnalysisTaskModel.status.in_(expected_statuses),
                ~AnalysisTaskModel.status.in_(TERMINAL_STATUSES),
            )
            .values(
                status=status,
                phase=phase,
                progress=progress,
                updated_at=now,
                completed_at=completed_at,
                **terminal_values,
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            return False
        await self.append_event(lease.task_id, event_type, payload or {}, now)
        return True

    async def finalize(
        self,
        lease: Lease,
        *,
        expected_statuses: set[str],
        status: str,
        phase: str,
        now: datetime,
        report: dict[str, Any] | None,
        report_version: int,
        schema_version: str,
        errors: tuple[str, ...] = (),
    ) -> bool:
        if status not in TERMINAL_STATUSES - {"CANCELLED"}:
            raise ValueError("worker finalization requires a worker terminal status")
        if (report is None) != (status in {"FAILED", "TIMEOUT"}):
            raise ValueError("report presence must match the terminal status")
        event_type = {
            "COMPLETED": "analysis_completed",
            "PARTIAL_RESULT": "analysis_partial",
            "FAILED": "analysis_failed",
            "TIMEOUT": "analysis_failed",
        }[status]
        result = await self._session.execute(
            update(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.id == lease.task_id,
                AnalysisTaskModel.fence == lease.fence,
                AnalysisTaskModel.lease_token == lease.token,
                AnalysisTaskModel.lease_deadline >= now,
                AnalysisTaskModel.status.in_(expected_statuses),
                ~AnalysisTaskModel.status.in_(TERMINAL_STATUSES),
            )
            .values(
                status=status,
                phase=phase,
                progress=100,
                updated_at=now,
                completed_at=now,
                lease_token=None,
                lease_deadline=None,
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            return False
        payload: dict[str, Any] = {}
        if report is not None:
            await ReportRepository(self._session).add(
                lease.task_id,
                report_version,
                report,
                schema_version,
                now,
            )
            payload = {
                "reportVersion": report_version,
                "reportUrl": f"/api/ai/case-analysis/{lease.task_id}/report",
            }
            await self.append_event(lease.task_id, "report_generated", payload, now)
        elif errors:
            payload = {"errorCodes": list(errors)}
        await self.append_event(lease.task_id, event_type, payload, now)
        return True


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        task_id: str,
        version: int,
        report: dict[str, Any],
        schema_version: str,
        created_at: datetime,
    ) -> ReportModel:
        canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
        model = ReportModel(
            task_id=task_id,
            version=version,
            schema_version=schema_version,
            report_json=report,
            report_hash=hashlib.sha256(canonical.encode()).hexdigest(),
            created_at=created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_version(self, task_id: str, version: int) -> ReportModel | None:
        return cast(
            ReportModel | None,
            await self._session.scalar(
                select(ReportModel).where(
                    ReportModel.task_id == task_id,
                    ReportModel.version == version,
                )
            ),
        )

    async def latest(self, task_id: str) -> ReportModel | None:
        return cast(
            ReportModel | None,
            await self._session.scalar(
                select(ReportModel)
                .where(ReportModel.task_id == task_id)
                .order_by(ReportModel.version.desc())
                .limit(1)
            ),
        )


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_idempotency_key(
        self,
        task_id: str,
        idempotency_key: str,
    ) -> EngineerReviewModel | None:
        return cast(
            EngineerReviewModel | None,
            await self._session.scalar(
                select(EngineerReviewModel).where(
                    EngineerReviewModel.task_id == task_id,
                    EngineerReviewModel.idempotency_key == idempotency_key,
                )
            ),
        )

    async def add_revision(
        self,
        *,
        task_id: str,
        values: ReviewValues,
        idempotency_key: str,
        created_at: datetime,
    ) -> EngineerReviewModel:
        await self._session.scalar(
            select(AnalysisTaskModel.id)
            .where(AnalysisTaskModel.id == task_id)
            .with_for_update()
        )
        revision = await self._session.scalar(
            select(func.coalesce(func.max(EngineerReviewModel.revision), 0) + 1).where(
                EngineerReviewModel.task_id == task_id
            )
        )
        review = EngineerReviewModel(
            id=str(uuid4()),
            task_id=task_id,
            report_version=values.report_version,
            revision=int(revision or 1),
            status=values.status,
            helpful=values.helpful,
            confirmed_hypothesis_id=values.confirmed_hypothesis_id,
            root_cause=values.root_cause,
            comment=values.comment,
            reviewer_id=values.reviewer_id,
            idempotency_key=idempotency_key,
            created_at=created_at,
        )
        self._session.add(review)
        await self._session.flush()
        return review

    async def get_revision(
        self,
        task_id: str,
        revision: int,
    ) -> EngineerReviewModel | None:
        return cast(
            EngineerReviewModel | None,
            await self._session.scalar(
                select(EngineerReviewModel).where(
                    EngineerReviewModel.task_id == task_id,
                    EngineerReviewModel.revision == revision,
                )
            ),
        )

    async def latest(self, task_id: str) -> EngineerReviewModel | None:
        return cast(
            EngineerReviewModel | None,
            await self._session.scalar(
                select(EngineerReviewModel)
                .where(EngineerReviewModel.task_id == task_id)
                .order_by(EngineerReviewModel.revision.desc())
                .limit(1)
            ),
        )


class CaseBookArchiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_idempotency_key(
        self,
        task_id: str,
        idempotency_key: str,
    ) -> CaseBookArchiveModel | None:
        return cast(
            CaseBookArchiveModel | None,
            await self._session.scalar(
                select(CaseBookArchiveModel).where(
                    CaseBookArchiveModel.task_id == task_id,
                    CaseBookArchiveModel.idempotency_key == idempotency_key,
                )
            ),
        )

    async def add(
        self,
        *,
        archive_id: str,
        task_id: str,
        values: ArchiveValues,
        idempotency_key: str,
        now: datetime,
    ) -> CaseBookArchiveModel:
        archive = CaseBookArchiveModel(
            id=archive_id,
            task_id=task_id,
            review_id=values.review_id,
            idempotency_key=idempotency_key,
            external_id=values.external_id,
            status=values.status,
            error_code=values.error_code,
            created_at=now,
            updated_at=now,
        )
        self._session.add(archive)
        await self._session.flush()
        return archive
