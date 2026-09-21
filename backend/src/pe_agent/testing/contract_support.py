from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pe_agent.domain import (
    CaseContextRequest,
    DecisionPrimitive,
    DecisionRequest,
    DecisionResult,
    FdcRequest,
    LotYieldRequest,
    RecipeRequest,
    RequestScope,
    SimilarCasesRequest,
    SpcRequest,
    ToolEventsRequest,
    ToolResult,
)
from pe_agent.ports import DecisionPort, PlatformDataPort
from pe_agent.testing.scenarios import Scenario


async def exercise_platform_contract(
    port: PlatformDataPort,
    scenario: Scenario,
    *,
    now: datetime,
) -> tuple[ToolResult[Any], ...]:
    scope = RequestScope(
        tenant_id="synthetic-tenant",
        user_id="synthetic-user",
        permissions=scenario.permission_profile.permissions,
        authorized_entity_ids=frozenset(
            {
                scenario.case.case_id,
                *scenario.case.lot_ids,
                *scenario.case.tool_ids,
                *scenario.case.recipe_ids,
            }
        ),
    )
    context = await port.get_case_context(
        CaseContextRequest(
            scope=scope,
            case_id=scenario.case.case_id,
            case_version=scenario.case.case_version,
        )
    )
    if context.case != scenario.case:
        raise AssertionError("platform returned a different case snapshot")

    lot_id = scenario.case.lot_ids[0]
    tool_id = scenario.case.tool_ids[0] if scenario.case.tool_ids else "SYN-TOOL"
    recipe_id = scenario.case.recipe_ids[0] if scenario.case.recipe_ids else "SYN-RECIPE"
    start_at = now - timedelta(hours=1)
    results: list[ToolResult[Any]] = []
    for tool_name in scenario.tool_results:
        if tool_name == "get_lot_yield":
            result: ToolResult[Any] = await port.get_lot_yield(
                LotYieldRequest(
                    scope=scope,
                    lot_id=lot_id,
                    process_step=scenario.case.process_step,
                    start_at=start_at,
                    end_at=now,
                )
            )
        elif tool_name == "get_tool_events":
            result = await port.get_tool_events(
                ToolEventsRequest(
                    scope=scope,
                    tool_id=tool_id,
                    start_at=start_at,
                    end_at=now,
                )
            )
        elif tool_name == "get_recipe_snapshot":
            result = await port.get_recipe_snapshot(
                RecipeRequest(scope=scope, recipe_id=recipe_id, effective_at=now)
            )
        elif tool_name == "get_spc_evidence":
            result = await port.get_spc_evidence(
                SpcRequest(
                    scope=scope,
                    tool_id=tool_id,
                    start_at=start_at,
                    end_at=now,
                )
            )
        elif tool_name == "get_fdc_evidence":
            result = await port.get_fdc_evidence(
                FdcRequest(
                    scope=scope,
                    tool_id=tool_id,
                    start_at=start_at,
                    end_at=now,
                )
            )
        elif tool_name == "search_similar_cases":
            result = await port.search_similar_cases(
                SimilarCasesRequest(
                    scope=scope,
                    case_type="YIELD_DROP",
                    process_step=scenario.case.process_step,
                )
            )
        else:
            raise AssertionError(f"contract does not recognize tool {tool_name}")
        if result.tool_id != tool_name:
            raise AssertionError("platform result toolId does not match its call")
        fixture = scenario.tool_results[tool_name]
        if result.status is not fixture.status:
            raise AssertionError("platform result status does not match fixture contract")
        if result.quality.completeness != fixture.completeness:
            raise AssertionError("platform result completeness does not match fixture contract")
        if result.evidence != fixture.evidence:
            raise AssertionError("platform result must preserve canonical fixture evidence")
        if tuple(item.evidence_id for item in result.evidence) != fixture.evidence_ids:
            raise AssertionError("platform result evidence IDs do not match fixture contract")
        for item in result.evidence:
            if item.event_time.tzinfo is None or item.event_time.utcoffset() is None:
                raise AssertionError("evidence eventTime must be timezone-aware")
            if item.retrieved_at.tzinfo is None or item.retrieved_at.utcoffset() is None:
                raise AssertionError("evidence retrievedAt must be timezone-aware")
            if item.retrieved_at < item.event_time:
                raise AssertionError("evidence cannot be retrieved before its event time")
            if not item.raw_ref.startswith("/api/ai/source-links/"):
                raise AssertionError("evidence rawRef must use the safe source-link route")
        if result.retrieved_at.tzinfo is None or result.retrieved_at.utcoffset() is None:
            raise AssertionError("platform result timestamp must be timezone-aware")
        if fixture.error_code is None:
            if result.error is not None or result.source is None:
                raise AssertionError("available platform result must include source and no error")
            if result.source.adapter_version != port.adapter_version:
                raise AssertionError("source metadata must preserve adapter version")
            if result.data is None:
                raise AssertionError("available platform result must contain canonical data")
        else:
            if result.error is None or result.error.code is not fixture.error_code:
                raise AssertionError("platform error code does not match fixture contract")
            if result.error.retryable is not fixture.retryable:
                raise AssertionError("platform retryability does not match fixture contract")
        results.append(result)
    return tuple(results)


async def exercise_decision_contract(
    port: DecisionPort,
    request: DecisionRequest,
) -> DecisionResult:
    result = await port.decide(request)
    expected_ids = {question.question_id for question in request.questions}
    actual_ids = {answer.question_id for answer in result.answers}
    if len(actual_ids) != len(result.answers):
        raise AssertionError("decision result contains duplicate question IDs")
    if actual_ids != expected_ids:
        raise AssertionError("decision result must answer every requested question exactly once")
    if result.requested_model != request.requested_model:
        raise AssertionError("decision result must preserve the requested model")
    if result.question_set_version != request.question_set_version:
        raise AssertionError("decision result must preserve the question-set version")
    questions = {question.question_id: question for question in request.questions}
    for answer in result.answers:
        question = questions[answer.question_id]
        if answer.primitive is not question.primitive:
            raise AssertionError("decision answer primitive must match its question")
        if question.primitive is DecisionPrimitive.CHOICE:
            if not isinstance(answer.answer, str):
                raise AssertionError("choice answer must be a string")
            choices = set(question.criteria)
            if answer.answer not in choices or set(answer.distribution) - choices:
                raise AssertionError("choice answer and distribution must use declared choices")
        elif question.primitive is DecisionPrimitive.SCORE and not isinstance(
            answer.answer, float
        ):
            raise AssertionError("score answer must be numeric")
        elif question.primitive is DecisionPrimitive.NOUL:
            if not isinstance(answer.answer, float) or not 0.0 <= answer.answer <= 1.0:
                raise AssertionError("Noul answer must be a probability")
            choices = set(question.criteria)
            if set(answer.distribution) - choices:
                raise AssertionError("Noul distribution must use declared outcomes")
    return result
