from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.adapters.persistence.repositories import Lease
from pe_agent.application.yield_drop_workflow import YieldDropWorkflow
from pe_agent.domain import (
    DecisionAnswer,
    DecisionPrimitive,
    DecisionRequest,
    DecisionResult,
    DecisionUsage,
    ExplanationRequest,
    ExplanationResult,
    ReportOutcome,
    TaskStatus,
)
from pe_agent.testing import load_scenario
from pe_agent.worker.service import WorkerRunner, WorkItem

FIXTURES = Path(__file__).parents[2] / "fixtures" / "scenarios"
NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


class FakeCoordinator:
    def __init__(self, work: WorkItem | None, *, accepts_finalize: bool = True) -> None:
        self.work = work
        self.accepts_finalize = accepts_finalize
        self.claims: list[tuple[datetime, timedelta]] = []
        self.finalizations: list[tuple[WorkItem, ReportOutcome, datetime]] = []

    async def claim(self, now: datetime, lease_duration: timedelta) -> WorkItem | None:
        self.claims.append((now, lease_duration))
        work, self.work = self.work, None
        return work

    async def finalize(
        self, work: WorkItem, outcome: ReportOutcome, now: datetime
    ) -> bool:
        self.finalizations.append((work, outcome, now))
        return self.accepts_finalize


class CapturingDecisionPort:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.requests: list[DecisionRequest] = []
        self.error = error

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return DecisionResult(
            requested_model=request.requested_model,
            resolved_model=request.requested_model,
            question_set_version=request.question_set_version,
            answers=(
                DecisionAnswer(
                    question_id="pressure_drift_support",
                    primitive=DecisionPrimitive.SCORE,
                    answer=2.72,
                    distribution={
                        "0": 0.01,
                        "1": 0.04,
                        "2": 0.17,
                        "3": 0.78,
                    },
                    confidence=0.71,
                ),
            ),
            usage=DecisionUsage(input_tokens=10, output_tokens=5, latency_ms=1),
        )


class BlockingDecisionPort:
    async def decide(self, request: DecisionRequest) -> DecisionResult:
        del request
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class CapturingExplanationPort:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.requests: list[ExplanationRequest] = []
        self.error = error

    async def explain(self, request: ExplanationRequest) -> ExplanationResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ExplanationResult(
            text="Cited observations remain the authority for engineer review.",
            requested_model="synthetic-model",
            resolved_model="synthetic-model-2026-09",
            input_tokens=10,
            output_tokens=8,
            latency_ms=2,
        )


def _work(scenario_name: str = "pressure-drift-success") -> tuple[WorkItem, Any]:
    scenario = load_scenario(FIXTURES / f"{scenario_name}.json")
    return (
        WorkItem(
            lease=Lease(
                task_id="SYN-TASK-001",
                token="synthetic-lease",
                fence=1,
                deadline=NOW + timedelta(seconds=60),
            ),
            tenant_id="synthetic-tenant",
            user_id="synthetic-engineer",
            permissions=scenario.permission_profile.permissions,
            authorized_entity_ids=frozenset(
                {
                    scenario.case.case_id,
                    *scenario.case.lot_ids,
                    *scenario.case.tool_ids,
                    *scenario.case.recipe_ids,
                }
            ),
            case_id=scenario.case.case_id,
            case_version=scenario.case.case_version,
            model_version="jev-1.13.0",
            schema_version="1.0.0",
        ),
        scenario,
    )


def _runner(
    coordinator: FakeCoordinator,
    scenario: Any,
    decision_port: Any,
    *,
    explanation_port: Any = None,
    task_timeout: timedelta = timedelta(seconds=45),
) -> WorkerRunner:
    return WorkerRunner(
        coordinator,
        YieldDropWorkflow(MockPlatformAdapter(scenario, clock=lambda: NOW)),
        decision_port,
        explanation_port=explanation_port,
        lease_duration=timedelta(seconds=60),
        task_timeout=task_timeout,
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_run_once_returns_false_when_no_task_is_available() -> None:
    coordinator = FakeCoordinator(None)
    decision = CapturingDecisionPort()
    _, scenario = _work()

    processed = await _runner(coordinator, scenario, decision).run_once()

    assert not processed
    assert coordinator.finalizations == []
    assert decision.requests == []


@pytest.mark.asyncio
async def test_run_once_collects_decides_and_finalizes_completed_report() -> None:
    work, scenario = _work()
    coordinator = FakeCoordinator(work)
    decision = CapturingDecisionPort()

    processed = await _runner(coordinator, scenario, decision).run_once()

    assert processed
    assert len(coordinator.finalizations) == 1
    outcome = coordinator.finalizations[0][1]
    assert outcome.terminal_status is TaskStatus.COMPLETED
    assert outcome.report is not None
    assert len(decision.requests) == 1
    request = decision.requests[0]
    assert request.state["synthetic"] is True
    assert set(request.state) == {
        "caseId",
        "evidenceIds",
        "evidenceSummaries",
        "hypothesis",
        "synthetic",
    }
    assert all(
        set(summary) == {
            "evidenceId",
            "kind",
            "observation",
            "quality",
            "warnings",
        }
        for summary in request.state["evidenceSummaries"]
    )
    assert "rawRef" not in str(request.state)
    assert "sourceId" not in str(request.state)


@pytest.mark.asyncio
async def test_explanation_is_non_authoritative_and_receives_whitelisted_report_view() -> None:
    work, scenario = _work()
    coordinator = FakeCoordinator(work)
    explanation = CapturingExplanationPort()

    await _runner(
        coordinator,
        scenario,
        CapturingDecisionPort(),
        explanation_port=explanation,
    ).run_once()

    outcome = coordinator.finalizations[0][1]
    assert outcome.terminal_status is TaskStatus.COMPLETED
    assert outcome.report is not None
    assert outcome.report["expression"]["nonAuthoritative"] is True
    assert "evidence" not in explanation.requests[0].report_view
    assert "rawRef" not in str(explanation.requests[0].report_view)


@pytest.mark.asyncio
async def test_explanation_failure_keeps_canonical_report() -> None:
    work, scenario = _work()
    coordinator = FakeCoordinator(work)

    await _runner(
        coordinator,
        scenario,
        CapturingDecisionPort(),
        explanation_port=CapturingExplanationPort(error=RuntimeError("secret body")),
    ).run_once()

    outcome = coordinator.finalizations[0][1]
    assert outcome.terminal_status is TaskStatus.COMPLETED
    assert outcome.report is not None
    assert "expression" not in outcome.report
    assert "secret" not in str(outcome)


@pytest.mark.asyncio
async def test_insufficient_evidence_skips_decision_and_fails_without_report() -> None:
    work, scenario = _work("insufficient-evidence")
    coordinator = FakeCoordinator(work)
    decision = CapturingDecisionPort()

    await _runner(coordinator, scenario, decision).run_once()

    outcome = coordinator.finalizations[0][1]
    assert outcome.terminal_status is TaskStatus.FAILED
    assert outcome.report is None
    assert outcome.validation_errors == ("INSUFFICIENT_EVIDENCE",)
    assert decision.requests == []


@pytest.mark.asyncio
async def test_decision_failure_is_sanitized_and_finalized() -> None:
    work, scenario = _work()
    coordinator = FakeCoordinator(work)
    decision = CapturingDecisionPort(error=RuntimeError("secret downstream body"))

    await _runner(coordinator, scenario, decision).run_once()

    outcome = coordinator.finalizations[0][1]
    assert outcome.terminal_status is TaskStatus.FAILED
    assert outcome.report is None
    assert outcome.validation_errors == ("ANALYSIS_FAILED",)
    assert "secret" not in str(outcome)


@pytest.mark.asyncio
async def test_task_timeout_is_sanitized_and_finalized() -> None:
    work, scenario = _work()
    coordinator = FakeCoordinator(work)

    await _runner(
        coordinator,
        scenario,
        BlockingDecisionPort(),
        task_timeout=timedelta(milliseconds=1),
    ).run_once()

    outcome = coordinator.finalizations[0][1]
    assert outcome.terminal_status is TaskStatus.TIMEOUT
    assert outcome.report is None
    assert outcome.validation_errors == ("ANALYSIS_TIMEOUT",)


@pytest.mark.asyncio
async def test_stale_finalize_is_not_retried_without_a_new_claim() -> None:
    work, scenario = _work()
    coordinator = FakeCoordinator(work, accepts_finalize=False)

    assert await _runner(coordinator, scenario, CapturingDecisionPort()).run_once()

    assert len(coordinator.claims) == 1
    assert len(coordinator.finalizations) == 1
