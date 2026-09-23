from __future__ import annotations

import logging
import os

import httpx
import pytest

from pe_agent.adapters.decisions import PINNED_TYPESAFE_MODEL, TypeSafeDecisionAdapter
from pe_agent.domain import DecisionPrimitive, DecisionQuestion, DecisionRequest

LOGGER = logging.getLogger(__name__)


@pytest.mark.live
@pytest.mark.asyncio
async def test_typesafe_single_synthetic_noul_smoke() -> None:
    if os.getenv("PE_AGENT_RUN_TYPESAFE_LIVE") != "1" or not os.getenv(
        "PE_AGENT_TYPESAFE_API_KEY"
    ):
        pytest.skip(
            "set PE_AGENT_RUN_TYPESAFE_LIVE=1 and PE_AGENT_TYPESAFE_API_KEY "
            "to run live TypeSafe smoke"
        )

    api_key = os.environ["PE_AGENT_TYPESAFE_API_KEY"]
    endpoint = os.getenv(
        "PE_AGENT_TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1/systemone"
    )
    request = DecisionRequest(
        state={
            "synthetic": True,
            "caseId": "SYN-LIVE-NOUL",
            "evidenceSummaries": [
                {
                    "evidenceId": "EV-SYN-LIVE-1",
                    "summary": (
                        "No case-specific countercheck has been supplied in this "
                        "synthetic test."
                    ),
                }
            ],
        },
        questions=(
            DecisionQuestion(
                question_id="needs_more_evidence",
                primitive=DecisionPrimitive.NOUL,
                instructions=(
                    "Does this explicitly synthetic hypothesis require more case-specific "
                    "evidence before an engineer should rely on it?"
                ),
                criteria={
                    "true": "Important case-specific evidence is missing",
                    "false": "Relevant case-specific support and counterchecks are present",
                },
            ),
        ),
        requested_model=PINNED_TYPESAFE_MODEL,
        question_set_version="synthetic-live-noul-v1",
    )

    async with httpx.AsyncClient() as client:
        result = await TypeSafeDecisionAdapter(
            endpoint_url=endpoint,
            api_key=api_key,
            client=client,
        ).decide(request)

    # Never log state, questions, answers, credentials, or HTTP bodies in this smoke test.
    LOGGER.info("TypeSafe resolved_model=%s usage=%s", result.resolved_model, result.usage)
    assert result.answers[0].primitive is DecisionPrimitive.NOUL
