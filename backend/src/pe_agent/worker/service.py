from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pe_agent.adapters.explanations import ExplanationError
from pe_agent.adapters.persistence.repositories import (
    ACTIVE_STATUSES,
    STAGE_COLLECTED,
    STAGE_DECIDED,
    Lease,
    TaskCheckpointRepository,
    TaskRepository,
)
from pe_agent.application.reporting import attach_expression, compose_report
from pe_agent.application.yield_drop_workflow import WorkflowCollection, YieldDropWorkflow
from pe_agent.domain import (
    DecisionPrimitive,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
    Evidence,
    EvidenceKind,
    ExplanationRequest,
    ReportInput,
    ReportOutcome,
    TaskStatus,
)
from pe_agent.ports import DecisionPort, ExplanationPort

Clock = Callable[[], datetime]
QUESTION_SET_VERSION = "yield-drop-jev-v1.0.0"
LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class AnalysisResult:
    outcome: ReportOutcome
    collection: WorkflowCollection | None
    decision: DecisionResult | None


class WorkerCoordinator(Protocol):
    async def claim(self, now: datetime, lease_duration: timedelta) -> WorkItem | None: ...

    async def finalize(
        self,
        work: WorkItem,
        outcome: ReportOutcome,
        now: datetime,
        *,
        tool_results: tuple[object, ...] = (),
        decision: object | None = None,
    ) -> bool: ...

    async def renew_lease(
        self,
        work: WorkItem,
        now: datetime,
        lease_duration: timedelta,
    ) -> bool:
        """Extend the active lease. Returns False if the lease can no longer be
        renewed (e.g. it already expired or was superseded by another worker)."""
        ...

    async def save_checkpoint(
        self,
        work: WorkItem,
        stage: str,
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        """Persist an intermediate stage payload so a restarted worker can resume."""
        ...

    async def load_checkpoint(
        self, work: WorkItem, stage: str
    ) -> dict[str, Any] | None:
        """Return a previously saved stage payload, or None if no checkpoint exists."""
        ...


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

    async def renew_lease(
        self,
        work: WorkItem,
        now: datetime,
        lease_duration: timedelta,
    ) -> bool:
        async with self._session_factory.begin() as session:
            return await TaskRepository(session).renew_lease(
                work.lease, now, lease_duration
            )

    async def save_checkpoint(
        self,
        work: WorkItem,
        stage: str,
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        async with self._session_factory.begin() as session:
            await TaskCheckpointRepository(session).save(
                task_id=work.lease.task_id,
                stage=stage,
                payload=payload,
                fence=work.lease.fence,
                now=now,
            )

    async def load_checkpoint(
        self, work: WorkItem, stage: str
    ) -> dict[str, Any] | None:
        async with self._session_factory.begin() as session:
            return await TaskCheckpointRepository(session).load(
                work.lease.task_id, stage
            )

    async def finalize(
        self,
        work: WorkItem,
        outcome: ReportOutcome,
        now: datetime,
        *,
        tool_results: tuple[object, ...] = (),
        decision: object | None = None,
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
                tool_results=tool_results,
                decision=decision,
            )


class WorkerRunner:
    def __init__(
        self,
        coordinator: WorkerCoordinator,
        workflow: YieldDropWorkflow,
        decision_port: DecisionPort,
        *,
        explanation_port: ExplanationPort | None = None,
        lease_duration: timedelta = timedelta(seconds=60),
        task_timeout: timedelta = timedelta(seconds=45),
        clock: Clock | None = None,
        renewal_interval: timedelta | None = None,
    ) -> None:
        if lease_duration.total_seconds() <= 0 or task_timeout.total_seconds() <= 0:
            raise ValueError("worker durations must be positive")
        if task_timeout >= lease_duration:
            raise ValueError("task timeout must be shorter than the lease duration")
        self._coordinator = coordinator
        self._workflow = workflow
        self._decision_port = decision_port
        self._explanation_port = explanation_port
        self._lease_duration = lease_duration
        self._task_timeout = task_timeout
        self._clock = clock or (lambda: datetime.now(UTC))
        # By default renew at half the lease so the lease never lapses while a
        # task is in flight; callers (and tests) may override the cadence.
        self._renewal_interval = renewal_interval or (lease_duration / 2)

    async def run_once(self) -> bool:
        work = await self._coordinator.claim(self._now(), self._lease_duration)
        if work is None:
            return False
        analysis: AnalysisResult | None = None
        # Renew the lease periodically so a slow task (e.g. a slow LLM
        # explanation) does not let its lease lapse before finalize.
        renewer = self._renew_lease_loop(work, self._renewal_interval.total_seconds())
        try:
            async with asyncio.timeout(self._task_timeout.total_seconds()):
                analysis = await self._analyze_full(work)
        except TimeoutError:
            outcome = ReportOutcome(
                None,
                TaskStatus.TIMEOUT,
                ("ANALYSIS_TIMEOUT",),
            )
        except Exception as exc:
            LOGGER.error("analysis_failed error_type=%s", type(exc).__name__)
            outcome = ReportOutcome(
                None,
                TaskStatus.FAILED,
                ("ANALYSIS_FAILED",),
            )
        else:
            outcome = analysis.outcome
        finally:
            renewer.cancel()
            with suppress(asyncio.CancelledError):
                await renewer
        tool_results = analysis.collection.results if analysis and analysis.collection else ()
        decision = analysis.decision if analysis else None
        await self._coordinator.finalize(
            work,
            outcome,
            self._now(),
            tool_results=tool_results,
            decision=decision,
        )
        return True

    def _renew_lease_loop(
        self, work: WorkItem, interval_seconds: float
    ) -> asyncio.Task[None]:
        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    renewed = await self._coordinator.renew_lease(
                        work, self._now(), self._lease_duration
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "lease_renewal_failed task=%s error_type=%s",
                        work.lease.task_id,
                        type(exc).__name__,
                    )
                    continue
                if not renewed:
                    LOGGER.warning(
                        "lease_lost task=%s (superseded or terminal)",
                        work.lease.task_id,
                    )
                    return

        return asyncio.ensure_future(_loop())

    async def _analyze_full(self, work: WorkItem) -> AnalysisResult:
        # Resume semantics: a restart re-claims the task with a higher fence.
        # If the previous worker already saved a "collected" checkpoint, reuse
        # it instead of redoing the (potentially expensive) platform calls; if
        # it also saved a "decided" checkpoint, reuse that too. Missing stages
        # fall through to live recomputation.
        collection: WorkflowCollection | None = None
        resumed_decision: DecisionResult | None = None
        if work.lease.fence > 1:
            collection = await self._load_collected_checkpoint(work)
            if collection is not None:
                LOGGER.info(
                    "resume task=%s stage=collected (fence=%d)",
                    work.lease.task_id,
                    work.lease.fence,
                )
            resumed_decision = await self._load_decided_checkpoint(work)
            if resumed_decision is not None:
                LOGGER.info(
                    "resume task=%s stage=decided (fence=%d)",
                    work.lease.task_id,
                    work.lease.fence,
                )
        if collection is None:
            collection = await self._collect(work)
            try:
                await self._coordinator.save_checkpoint(
                    work,
                    STAGE_COLLECTED,
                    _collection_payload(collection),
                    self._now(),
                )
            except Exception as exc:
                LOGGER.warning(
                    "checkpoint_save_failed stage=collected task=%s error_type=%s",
                    work.lease.task_id,
                    type(exc).__name__,
                )
        outcome, decision = await self._analyze(
            work, collection, prior_decision=resumed_decision
        )
        return AnalysisResult(outcome=outcome, collection=collection, decision=decision)

    async def _load_collected_checkpoint(
        self, work: WorkItem
    ) -> WorkflowCollection | None:
        payload = await self._coordinator.load_checkpoint(work, STAGE_COLLECTED)
        if payload is None:
            return None
        try:
            return _collection_from_payload(payload)
        except Exception as exc:
            LOGGER.warning(
                "checkpoint_invalid stage=collected task=%s error_type=%s",
                work.lease.task_id,
                type(exc).__name__,
            )
            return None

    async def _load_decided_checkpoint(self, work: WorkItem) -> DecisionResult | None:
        payload = await self._coordinator.load_checkpoint(work, STAGE_DECIDED)
        if payload is None:
            return None
        try:
            import json

            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            return DecisionResult.model_validate_json(canonical)
        except Exception as exc:
            LOGGER.warning(
                "checkpoint_invalid stage=decided task=%s error_type=%s",
                work.lease.task_id,
                type(exc).__name__,
            )
            return None

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
        *,
        prior_decision: DecisionResult | None = None,
    ) -> tuple[ReportOutcome, DecisionResult | None]:
        current_evidence = tuple(
            item
            for result in collection.results
            for item in result.evidence
            if item.kind is not EvidenceKind.HISTORICAL_CASE
        )
        if prior_decision is not None and current_evidence:
            decision = prior_decision
        elif current_evidence:
            decision = await self._decision_port.decide(
                _decision_request(
                    work,
                    current_evidence,
                    synthetic=collection.context.case.synthetic,
                )
            )
        else:
            decision = None
        resolved_model = work.model_version
        if decision is not None:
            resolved_model = decision.resolved_model
            try:
                await self._coordinator.save_checkpoint(
                    work,
                    STAGE_DECIDED,
                    decision.model_dump(mode="json"),
                    self._now(),
                )
            except Exception as exc:
                LOGGER.warning(
                    "checkpoint_save_failed stage=decided task=%s error_type=%s",
                    work.lease.task_id,
                    type(exc).__name__,
                )
        outcome = compose_report(
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
        if outcome.report is None or self._explanation_port is None:
            return outcome, decision
        try:
            explanation = await self._explanation_port.explain(
                ExplanationRequest(
                    report_view=_explanation_view(outcome.report),
                    synthetic=collection.context.case.synthetic,
                )
            )
        except ExplanationError as exc:
            LOGGER.warning("explanation_unavailable error_type=%s", type(exc).__name__)
            return outcome, decision
        except Exception as exc:
            LOGGER.error("explanation_unavailable error_type=%s", type(exc).__name__)
            return outcome, decision
        return (
            attach_expression(
                outcome,
                expression={
                    "provider": "openai-compatible",
                    "requestedModel": explanation.requested_model,
                    "resolvedModel": explanation.resolved_model,
                    "text": explanation.text,
                    "nonAuthoritative": True,
                    "usage": {
                        "inputTokens": explanation.input_tokens,
                        "outputTokens": explanation.output_tokens,
                        "latencyMs": explanation.latency_ms,
                    },
                },
            ),
            decision,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("worker clock must return an aware timestamp")
        return now


def _explanation_view(report: dict[str, object]) -> dict[str, object]:
    return {
        key: report[key]
        for key in (
            "caseSnapshot",
            "summary",
            "impact",
            "findings",
            "correlations",
            "hypotheses",
            "recommendations",
            "uncertainties",
        )
        if key in report
    }


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
                "腔体压力（CHAMBER_PRESSURE）观测异常可能关联本次良率下降"
            ),
            "synthetic": synthetic,
        },
        questions=(
            DecisionQuestion(
                question_id="pressure_drift_support",
                primitive=DecisionPrimitive.SCORE,
                instructions=(
                    "评估现有证据对上述假设的支持强度；"
                    "仅评估支持度，不要推断因果或选择工具。"
                ),
                criteria=(
                    "INSUFFICIENT：证据缺失或不可用",
                    "WEAK：支持度低或存在更强反证",
                    "MIXED：支持度与反证并存且均有分量",
                    "STRONG：多条独立证据支持且无实质反证",
                ),
            ),
        ),
        requested_model=work.model_version,
        question_set_version=QUESTION_SET_VERSION,
    )


def _collection_payload(collection: WorkflowCollection) -> dict[str, Any]:
    """Serialize a WorkflowCollection into a JSON-safe dict for a checkpoint row.

    CaseContext, ToolResult, and Evidence are all pydantic models, so
    model_dump(mode="json") produces a fully JSON-safe payload.
    """
    return {
        "context": collection.context.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in collection.results],
        "skipped_sources": list(collection.skipped_sources),
    }


def _collection_from_payload(payload: dict[str, Any]) -> WorkflowCollection:
    """Reconstruct a WorkflowCollection from a saved checkpoint payload.

    Domain models use strict validation, so model_validate on a JSON-dumped
    dict rejects enum/str coercion. Serialize the payload back to a JSON
    string and use model_validate_json (lax mode) which accepts it.
    Raises on any schema mismatch so the caller can fall back to a fresh
    collect rather than resume with corrupt data.
    """
    import json

    from pe_agent.domain import CaseContext, ToolResult

    raw_context = payload["context"]
    raw_results = payload.get("results", [])
    raw_skipped = payload.get("skipped_sources", [])

    # Round-trip each sub-object through json so enum strings coerce back.
    context = CaseContext.model_validate_json(
        json.dumps(raw_context, sort_keys=True, separators=(",", ":"))
    )
    results: tuple[ToolResult[object], ...] = tuple(
        ToolResult.model_validate_json(
            json.dumps(item, sort_keys=True, separators=(",", ":"))
        )
        for item in raw_results
    )
    return WorkflowCollection(
        context=context,
        results=results,
        skipped_sources=tuple(raw_skipped),
    )
