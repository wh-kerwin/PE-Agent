from __future__ import annotations

import pytest

from pe_agent.domain import (
    DecisionAnswer,
    DecisionPrimitive,
    DecisionQuestion,
    DecisionRequest,
    DecisionResult,
    DecisionUsage,
)
from pe_agent.testing import exercise_decision_contract


class RecordedDecisionAdapter:
    async def decide(self, request: DecisionRequest) -> DecisionResult:
        return DecisionResult(
            requested_model=request.requested_model,
            resolved_model="synthetic-recorded-v1",
            question_set_version=request.question_set_version,
            answers=(
                DecisionAnswer(
                    question_id="next_branch",
                    primitive=DecisionPrimitive.CHOICE,
                    answer="SPC_FDC",
                    distribution={"SPC_FDC": 0.8, "INSUFFICIENT_CONTEXT": 0.2},
                    confidence=0.6,
                ),
            ),
            usage=DecisionUsage(input_tokens=10, output_tokens=5, latency_ms=1),
        )


@pytest.mark.asyncio
async def test_recorded_adapter_passes_reusable_decision_contract() -> None:
    request = DecisionRequest(
        state={"synthetic": True, "evidenceIds": ["EV-SYN-1"]},
        questions=(
            DecisionQuestion(
                question_id="next_branch",
                primitive=DecisionPrimitive.CHOICE,
                instructions="Choose the next synthetic investigation branch.",
                criteria={
                    "SPC_FDC": "Inspect synthetic signals",
                    "INSUFFICIENT_CONTEXT": "Report an evidence gap",
                },
            ),
        ),
        requested_model="synthetic-recorded-v1",
        question_set_version="synthetic-question-set-v1",
    )

    result = await exercise_decision_contract(RecordedDecisionAdapter(), request)

    assert result.resolved_model == "synthetic-recorded-v1"
