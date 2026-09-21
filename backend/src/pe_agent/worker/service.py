from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pe_agent.adapters.persistence.repositories import ACTIVE_STATUSES, Lease, TaskRepository
from pe_agent.application.reporting import compose_report
from pe_agent.application.yield_drop_workflow import WorkflowCollection, YieldDropWorkflow
from pe_agent.domain import (
    DecisionPrimitive,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
    Evidence,
    EvidenceKind,
    ReportInput,
    ReportOutcome,
    TaskStatus,
)
from pe_agent.ports import DecisionPort

Clock = Callable[[], datetime]
QUESTION_SET_VERSION = "yield-drop-jev-v1.0.0"


@dataclass(frozen=True)
class WorkItem:
    lease: Lease
    tenant_id: str
    user_id: str
    permissions: frozenset[str]
    authorized_entity_ids: frozenset[str]
    case_id: str
    case_version: str
    model_version: str
    schema_version: str


class WorkerCoordinator(Protocol):
    async def claim(self, now: datetime, lease_duration: timedelta) -> WorkItem | None: ...

    async def finalize(
        self,
        work: WorkItem,
        outcome: ReportOutcome,
        now: datetime,
    ) -> bool: ...


class SqlWorkerCoordinator:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def claim(self, now: datetime, lease_duration: timedelta) -> WorkItem | None:
        async with self._session_factory.begin() as session:
            repository = TaskRepository(session)
            lease = await repository.claim(now, lease_duration)
            if lease is None:
                return None
            task = await repository.get(lease.task_id)
            return WorkItem(
                lease=lease,
                tenant_id=task.tenant_id,
                user_id=task.user_id,
                permissions=frozenset(task.permissions),
                authorized_entity_ids=frozenset(task.authorized_entity_ids),
                case_id=task.case_id,
                case_version=task.case_version,
                model_version=task.model_version,
                schema_version=task.schema_version,
            )

    async def finalize(
        self,
        work: WorkItem,
        outcome: ReportOutcome,
        now: datetime,
    ) -> bool:
        async with self._session_factory.begin() as session:
            return await TaskRepository(session).finalize(
                work.lease,
                expected_statuses=ACTIVE_STATUSES,
                status=outcome.terminal_status.value,
                phase="compose_and_validate_report",
                now=now,
                report=outcome.report,
                report_version=1,
                schema_version=work.schema_version,
                errors=outcome.validation_errors,
            )


class WorkerRunner:
    def __init__(
        self,
        coordinator: WorkerCoordinator,
        workflow: YieldDropWorkflow,
        decision_port: DecisionPort,
        *,
        lease_duration: timedelta = timedelta(seconds=60),
        task_timeout: timedelta = timedelta(seconds=45),
        clock: Clock | None = None,
    ) -> None:
        if lease_duration.total_seconds() <= 0 or task_timeout.total_seconds() <= 0:
            raise ValueError("worker durations must be positive")
        if task_timeout >= lease_duration:
            raise ValueError("task timeout must be shorter than the lease duration")
        self._coordinator = coordinator
        self._workflow = workflow
        self._decision_port = decision_port
        self._lease_duration = lease_duration
        self._task_timeout = task_timeout
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run_once(self) -> bool:
        work = await self._coordinator.claim(self._now(), self._lease_duration)
        if work is None:
            return False
        try:
            async with asyncio.timeout(self._task_timeout.total_seconds()):
                collection = await self._collect(work)
                outcome = await self._analyze(work, collection)
        except TimeoutError:
            outcome = ReportOutcome(
                None,
                TaskStatus.TIMEOUT,
                ("ANALYSIS_TIMEOUT",),
            )
        except Exception:
            outcome = ReportOutcome(
                None,
                TaskStatus.FAILED,
                ("ANALYSIS_FAILED",),
            )
        await self._coordinator.finalize(work, outcome, self._now())
        return True

    async def _collect(self, work: WorkItem) -> WorkflowCollection:
        return await self._workflow.collect(
            tenant_id=work.tenant_id,
            user_id=work.user_id,
            permissions=work.permissions,
            authorized_entity_ids=work.authorized_entity_ids,
            case_id=work.case_id,
            case_version=work.case_version,
        )

    async def _analyze(
        self,
        work: WorkItem,
        collection: WorkflowCollection,
    ) -> ReportOutcome:
        current_evidence = tuple(
            item
            for result in collection.results
            for item in result.evidence
            if item.kind is not EvidenceKind.HISTORICAL_CASE
        )
        decision: DecisionResult | None = None
        resolved_model = work.model_version
        if current_evidence:
            decision = await self._decision_port.decide(
                _decision_request(
                    work,
                    current_evidence,
                    synthetic=collection.context.case.synthetic,
                )
            )
            resolved_model = decision.resolved_model
        return compose_report(
            ReportInput(
                task_id=work.lease.task_id,
                report_version=1,
                context=collection.context,
                results=collection.results,
                skipped_sources=collection.skipped_sources,
                authorized_entity_ids=work.authorized_entity_ids,
                generated_at=self._now(),
                requested_model=work.model_version,
                resolved_model=resolved_model,
                question_set_version=QUESTION_SET_VERSION,
                decision=decision,
            )
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("worker clock must return an aware timestamp")
        return now


def _decision_request(
    work: WorkItem,
    evidence: tuple[Evidence, ...],
    *,
    synthetic: bool,
) -> DecisionRequest:
    normalized = [
        {
            "evidenceId": item.evidence_id,
            "kind": item.kind.value,
            "observation": item.observation,
            "quality": item.quality.value,
            "warnings": list(item.warnings),
        }
        for item in evidence
    ]
    return DecisionRequest(
        state={
            "caseId": work.case_id,
            "evidenceIds": [item["evidenceId"] for item in normalized],
            "evidenceSummaries": normalized,
            "hypothesis": (
                "Chamber-pressure observations may be associated with the yield loss"
            ),
            "synthetic": synthetic,
        },
        questions=(
            DecisionQuestion(
                question_id="pressure_drift_support",
                primitive=DecisionPrimitive.SCORE,
                instructions=(
                    "How strongly does the supplied evidence support the named hypothesis? "
                    "Evaluate support only; do not claim causation or select tools."
                ),
                criteria=(
                    "INSUFFICIENT: evidence is missing or unusable",
                    "WEAK: little support or stronger contradictions",
                    "MIXED: meaningful support and contradiction",
                    "STRONG: multiple supporting observations with no material contradiction",
                ),
            ),
        ),
        requested_model=work.model_version,
        question_set_version=QUESTION_SET_VERSION,
    )
