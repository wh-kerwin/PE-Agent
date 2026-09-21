from __future__ import annotations

import json
from pathlib import Path

import pytest

from pe_agent.adapters.decisions import PINNED_TYPESAFE_MODEL, RecordedDecisionAdapter
from pe_agent.domain import DecisionPrimitive, DecisionQuestion, DecisionRequest
from pe_agent.testing import exercise_decision_contract

FIXTURES = Path(__file__).parents[1] / "fixtures" / "decisions"
EXAMPLE_SCORE = Path(__file__).parents[3] / "examples" / "jev-assessment.json"


def _choice_request() -> DecisionRequest:
    return DecisionRequest(
        state={
            "caseId": "SYN-CHOICE-CASE",
            "evidenceSummaries": [
                {
                    "evidenceId": "EV-SYN-CHOICE-1",
                    "summary": "Synthetic SPC evidence is available while FDC is missing.",
                }
            ],
        },
        questions=(
            DecisionQuestion(
                question_id="next_branch",
                primitive=DecisionPrimitive.CHOICE,
                instructions="Choose the next synthetic investigation branch.",
                criteria={
                    "SPC_FDC": "Inspect synthetic process signals",
                    "INSUFFICIENT_CONTEXT": "Do not select a branch",
                },
            ),
        ),
        requested_model=PINNED_TYPESAFE_MODEL,
        question_set_version="synthetic-choice-v1",
    )


def _score_request() -> DecisionRequest:
    return DecisionRequest(
        state={
            "caseId": "CASE-20260920-001",
            "evidenceIds": ["EV-YIELD-01", "EV-SPC-01", "EV-FDC-01", "EV-PEER-01"],
        },
        questions=(
            DecisionQuestion(
                question_id="pressure_drift_support",
                primitive=DecisionPrimitive.SCORE,
                instructions=(
                    "How strongly does the supplied evidence support the named hypothesis that "
                    "chamber pressure drift contributed to this yield drop? Evaluate support, "
                    "not whether the hypothesis is proven."
                ),
                criteria=(
                    "INSUFFICIENT: evidence is missing or unusable",
                    "WEAK: little support or stronger contradictions",
                    "MIXED: meaningful support and contradiction",
                    "STRONG: multiple independent supporting observations with no "
                    "material contradiction",
                ),
            ),
        ),
        requested_model=PINNED_TYPESAFE_MODEL,
        question_set_version="yield-drop-jev-v1.0.0",
    )


def _noul_request() -> DecisionRequest:
    return DecisionRequest(
        state={
            "caseId": "SYN-NOUL-CASE",
            "evidenceSummaries": [
                {
                    "evidenceId": "EV-SYN-NOUL-1",
                    "summary": "Synthetic case-specific countercheck is absent.",
                }
            ],
        },
        questions=(
            DecisionQuestion(
                question_id="needs_more_evidence",
                primitive=DecisionPrimitive.NOUL,
                instructions="Does this synthetic hypothesis need more case-specific evidence?",
                criteria={
                    "true": "Important evidence is missing",
                    "false": "Relevant case-specific checks are present",
                },
            ),
        ),
        requested_model=PINNED_TYPESAFE_MODEL,
        question_set_version="synthetic-noul-v1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision_request", "expected_answer", "expected_distribution", "expected_confidence"),
    [
        (_choice_request(), "SPC_FDC", {"SPC_FDC": 0.8, "INSUFFICIENT_CONTEXT": 0.2}, 0.6),
        (_score_request(), 2.72, {"0": 0.01, "1": 0.04, "2": 0.17, "3": 0.78}, 0.71),
        (_noul_request(), 0.9, {"false": pytest.approx(0.1), "true": 0.9}, None),
    ],
)
async def test_recorded_adapter_normalizes_all_primitives_and_preserves_metadata(
    decision_request: DecisionRequest,
    expected_answer: str | float,
    expected_distribution: dict[str, object],
    expected_confidence: float | None,
) -> None:
    adapter = RecordedDecisionAdapter(
        (FIXTURES / "choice.json", EXAMPLE_SCORE, FIXTURES / "noul.json")
    )

    result = await exercise_decision_contract(adapter, decision_request)

    assert result.requested_model == PINNED_TYPESAFE_MODEL
    assert result.resolved_model == PINNED_TYPESAFE_MODEL
    assert result.question_set_version == decision_request.question_set_version
    assert result.answers[0].answer == expected_answer
    assert result.answers[0].distribution == expected_distribution
    assert result.answers[0].confidence == expected_confidence
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.latency_ms is None


@pytest.mark.asyncio
async def test_recorded_adapter_rejects_unmatched_state() -> None:
    adapter = RecordedDecisionAdapter((FIXTURES / "choice.json",))
    request = _choice_request().model_copy(update={"state": {"caseId": "OTHER"}})

    with pytest.raises(RuntimeError, match="exactly one synthetic recording"):
        await adapter.decide(request)


@pytest.mark.asyncio
async def test_recorded_adapter_rejects_question_version_mismatch() -> None:
    adapter = RecordedDecisionAdapter((FIXTURES / "choice.json",))
    request = _choice_request().model_copy(update={"question_set_version": "synthetic-choice-v2"})

    with pytest.raises(RuntimeError, match="exactly one synthetic recording"):
        await adapter.decide(request)


def test_all_recorded_fixtures_are_explicitly_synthetic() -> None:
    paths = [*FIXTURES.glob("*.json"), EXAMPLE_SCORE]
    assert all(json.loads(path.read_text(encoding="utf-8"))["synthetic"] is True for path in paths)
