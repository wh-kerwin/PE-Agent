from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.application.reporting import attach_expression, compose_report, validate_report
from pe_agent.application.yield_drop_workflow import WorkflowCollection, YieldDropWorkflow
from pe_agent.domain import (
    DecisionAnswer,
    DecisionPrimitive,
    DecisionResult,
    DecisionUsage,
    EntityReference,
    EntityType,
    ReportInput,
    ReportOutcome,
    TaskStatus,
)
from pe_agent.testing import load_scenario

FIXTURES = Path(__file__).parents[2] / "fixtures" / "scenarios"
AUTHORITATIVE_SCHEMA = (
    Path(__file__).parents[3] / "agent" / "schemas" / "analysis-report.schema.json"
)
PACKAGED_SCHEMA = Path(__file__).parents[2] / "src" / "pe_agent" / "analysis-report.schema.json"
NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
MODEL = "jev-1.13.0"
QUESTION_SET = "yield-drop-jev-v1.0.0"


def _scenario_entities(scenario: Any) -> frozenset[str]:
    case = scenario.case
    return frozenset(
        {case.case_id, *case.lot_ids, *case.tool_ids, *case.recipe_ids}
    )


async def _collection(scenario_name: str) -> WorkflowCollection:
    scenario = load_scenario(FIXTURES / f"{scenario_name}.json")
    return await YieldDropWorkflow(
        MockPlatformAdapter(scenario, clock=lambda: NOW)
    ).collect(
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=scenario.permission_profile.permissions,
        authorized_entity_ids=_scenario_entities(scenario),
        case_id=scenario.case.case_id,
        case_version=scenario.case.case_version,
    )


def _input(
    collection: WorkflowCollection,
    *,
    decision: DecisionResult | None = None,
) -> ReportInput:
    return ReportInput(
        task_id="SYN-TASK-001",
        report_version=1,
        context=collection.context,
        results=collection.results,
        skipped_sources=collection.skipped_sources,
        authorized_entity_ids=_authorized_entities(collection),
        generated_at=NOW,
        requested_model=MODEL,
        resolved_model=MODEL,
        question_set_version=QUESTION_SET,
        decision=decision,
    )


def _decision() -> DecisionResult:
    return DecisionResult(
        requested_model=MODEL,
        resolved_model=MODEL,
        question_set_version=QUESTION_SET,
        answers=(
            DecisionAnswer(
                question_id="pressure_drift_support",
                primitive=DecisionPrimitive.SCORE,
                answer=2.72,
                distribution={
                    "INSUFFICIENT": 0.01,
                    "WEAK": 0.04,
                    "MIXED": 0.17,
                    "STRONG": 0.78,
                },
                confidence=0.71,
            ),
        ),
        usage=DecisionUsage(input_tokens=10, output_tokens=5, latency_ms=1),
    )


def _authorized_entities(collection: WorkflowCollection) -> frozenset[str]:
    case = collection.context.case
    return frozenset(
        {case.case_id, *case.lot_ids, *case.tool_ids, *case.recipe_ids}
    )


def _validation_context(
    collection: WorkflowCollection,
) -> tuple[tuple[Any, ...], frozenset[str]]:
    evidence = tuple(item for result in collection.results for item in result.evidence)
    entities = _authorized_entities(collection)
    return evidence, entities


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario_name", "expected_status"),
    (
        ("pressure-drift-success", TaskStatus.COMPLETED),
        ("recipe-change", TaskStatus.COMPLETED),
        ("conflicting-sources", TaskStatus.PARTIAL_RESULT),
        ("fdc-timeout", TaskStatus.PARTIAL_RESULT),
        ("insufficient-evidence", TaskStatus.FAILED),
        ("history-mismatch", TaskStatus.PARTIAL_RESULT),
    ),
)
async def test_composer_matches_scenario_outcomes(
    scenario_name: str, expected_status: TaskStatus
) -> None:
    collection = await _collection(scenario_name)

    outcome = compose_report(
        _input(
            collection,
            decision=None if scenario_name == "insufficient-evidence" else _decision(),
        )
    )

    assert outcome.terminal_status is expected_status
    if expected_status is TaskStatus.FAILED:
        assert outcome.report is None
        assert outcome.validation_errors == ("INSUFFICIENT_EVIDENCE",)
    else:
        assert outcome.report is not None
        assert outcome.validation_errors == ()
        assert {
            item["evidenceId"] for item in outcome.report["evidence"]
        } == {
            item.evidence_id
            for result in collection.results
            for item in result.evidence
        }


@pytest.mark.asyncio
async def test_pressure_decision_produces_grounded_hypothesis() -> None:
    collection = await _collection("pressure-drift-success")

    outcome = compose_report(_input(collection, decision=_decision()))

    assert outcome.terminal_status is TaskStatus.COMPLETED
    assert outcome.report is not None
    hypothesis = outcome.report["hypotheses"][0]
    assert hypothesis["supportingEvidenceIds"] == ["EV-FDC-001", "EV-SPC-001"]
    assert hypothesis["modelAssessment"]["questionId"] == "pressure_drift_support"
    assert hypothesis["modelAssessment"]["resolvedModel"] == MODEL
    assert "confirmed" not in hypothesis["title"].lower()
    assert "caused" not in hypothesis["title"].lower()


@pytest.mark.asyncio
async def test_historical_mismatch_is_an_uncertainty_not_support() -> None:
    collection = await _collection("history-mismatch")

    outcome = compose_report(_input(collection, decision=_decision()))

    assert outcome.report is not None
    assert outcome.report["similarCases"] == []
    assert outcome.report["hypotheses"] == []
    assert all(
        "SYN-HIST-01" not in str(item)
        for section in ("findings", "correlations", "recommendations")
        for item in outcome.report[section]
    )
    assert any(
        "No history matched" in item["description"]
        for item in outcome.report["uncertainties"]
    )


@pytest.mark.asyncio
async def test_yield_conflict_fails_without_publishing_a_report() -> None:
    collection = await _collection("pressure-drift-success")
    yield_result = next(
        result for result in collection.results if result.tool_id == "get_lot_yield"
    )
    assert yield_result.data is not None
    conflicting = yield_result.model_copy(
        update={"data": yield_result.data.model_copy(update={"observed_percent": 83.0})}
    )
    collection = WorkflowCollection(
        context=collection.context,
        results=tuple(
            conflicting if result is yield_result else result
            for result in collection.results
        ),
        skipped_sources=collection.skipped_sources,
    )

    outcome = compose_report(_input(collection))

    assert outcome.report is None
    assert outcome.terminal_status is TaskStatus.FAILED
    assert "YIELD_EVIDENCE_CONFLICT" in outcome.validation_errors


@pytest.mark.asyncio
async def test_decision_metadata_mismatch_fails_closed() -> None:
    collection = await _collection("pressure-drift-success")
    decision = _decision().model_copy(update={"resolved_model": "jev-other"})

    outcome = compose_report(_input(collection, decision=decision))

    assert outcome.report is None
    assert outcome.terminal_status is TaskStatus.FAILED
    assert "DECISION_METADATA_MISMATCH" in outcome.validation_errors


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        (
            lambda report: report["findings"][0].update(
                {"evidenceIds": ["EV-NOT-PRESENT"]}
            ),
            "unknown evidence references",
        ),
        (
            lambda report: report["timeline"].reverse(),
            "timeline must be chronological",
        ),
        (
            lambda report: report["impact"]["yield"].update(
                {
                    "observedPercent": 1.0,
                    "baselinePercent": 2.0,
                    "absoluteDropPercentagePoints": 1.0,
                }
            ),
            "yield impact does not match canonical inputs",
        ),
        (
            lambda report: report["hypotheses"][0]["modelAssessment"].update(
                {"answer": 0.0}
            ),
            "does not preserve the decision result",
        ),
        (
            lambda report: report["summary"].update(
                {"overview": "The confirmed root cause was chamber pressure."}
            ),
            "unverified causal claim",
        ),
        (
            lambda report: report["evidence"][0].update(
                {"observation": "Tampered source observation"}
            ),
            "does not preserve its canonical source",
        ),
        (
            lambda report: report.update({"taskId": "OTHER-TASK"}),
            "identity metadata does not match",
        ),
        (
            lambda report: report["model"].update(
                {"resolvedModel": "unexpected-model"}
            ),
            "model metadata does not match",
        ),
    ),
)
async def test_semantic_validation_rejects_report_tampering(
    mutation: Any, expected_error: str
) -> None:
    collection = await _collection("pressure-drift-success")
    outcome = compose_report(_input(collection, decision=_decision()))
    assert outcome.report is not None
    report = copy.deepcopy(outcome.report)
    mutation(report)
    evidence, entities = _validation_context(collection)

    errors = validate_report(
        report,
        source_evidence=evidence,
        allowed_entity_ids=entities,
        expected_identity=(
            "SYN-TASK-001",
            1,
            collection.context.case.case_id,
            collection.context.case.case_version,
        ),
        expected_model=(MODEL, MODEL, QUESTION_SET),
        expected_yield=(82.0, 96.0, 14.0),
        decision=_decision(),
    )

    assert any(expected_error in error for error in errors)


@pytest.mark.asyncio
async def test_missing_decision_is_explicitly_partial() -> None:
    collection = await _collection("pressure-drift-success")

    outcome = compose_report(_input(collection))

    assert outcome.terminal_status is TaskStatus.PARTIAL_RESULT
    assert outcome.report is not None
    assert outcome.report["hypotheses"] == []
    assert any(
        item["description"] == "Model assessment was unavailable."
        for item in outcome.report["uncertainties"]
    )


@pytest.mark.asyncio
async def test_schema_invalid_report_returns_errors_without_crashing() -> None:
    collection = await _collection("pressure-drift-success")
    outcome = compose_report(_input(collection, decision=_decision()))
    assert outcome.report is not None
    report = copy.deepcopy(outcome.report)
    report["findings"] = "not-an-array"
    evidence, entities = _validation_context(collection)

    errors = validate_report(
        report,
        source_evidence=evidence,
        allowed_entity_ids=entities,
        expected_identity=(
            "SYN-TASK-001",
            1,
            collection.context.case.case_id,
            collection.context.case.case_version,
        ),
        expected_model=(MODEL, MODEL, QUESTION_SET),
        expected_yield=(82.0, 96.0, 14.0),
        decision=_decision(),
    )

    assert any("schema" in error for error in errors)


@pytest.mark.asyncio
async def test_unauthorized_wafer_reference_fails_closed() -> None:
    collection = await _collection("pressure-drift-success")
    first = collection.results[0]
    evidence = first.evidence[0].model_copy(
        update={
            "entity_refs": (
                EntityReference(type=EntityType.WAFER, id="OTHER-TENANT-WAFER"),
            )
        }
    )
    modified = first.model_copy(update={"evidence": (evidence,)})
    collection = WorkflowCollection(
        context=collection.context,
        results=(modified, *collection.results[1:]),
        skipped_sources=collection.skipped_sources,
    )

    outcome = compose_report(_input(collection, decision=_decision()))

    assert outcome.report is None
    assert outcome.terminal_status is TaskStatus.FAILED
    assert any("unauthorized entity" in error for error in outcome.validation_errors)


def test_expression_rejects_unverified_causal_language() -> None:
    outcome = ReportOutcome(
        {"schemaVersion": "1.0.0"},
        TaskStatus.COMPLETED,
    )

    for text in (
        "The root cause is chamber pressure.",
        "The loss occurred due to chamber pressure.",
        "因此该参数导致良率下降。",
    ):
        assert attach_expression(
            outcome,
            expression={"text": text},
        ) == outcome


def test_expression_is_attached_only_as_non_authoritative_schema_data() -> None:
    outcome = ReportOutcome(
        {"schemaVersion": "1.0.0"},
        TaskStatus.COMPLETED,
    )

    attached = attach_expression(
        outcome,
        expression={
            "provider": "openai-compatible",
            "requestedModel": "synthetic-model",
            "resolvedModel": "synthetic-model",
            "text": "Review the cited observations.",
            "nonAuthoritative": True,
            "usage": {"inputTokens": 1, "outputTokens": 2, "latencyMs": 3},
        },
    )

    assert attached == outcome


    assert PACKAGED_SCHEMA.read_bytes() == AUTHORITATIVE_SCHEMA.read_bytes()
