from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.application.yield_drop_workflow import YieldDropWorkflow
from pe_agent.domain import CaseContextRequest, ToolResult
from pe_agent.testing import load_scenario

FIXTURES = Path(__file__).parents[2] / "fixtures" / "scenarios"
NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
EXECUTABLE_SCENARIOS = (
    "pressure-drift-success",
    "recipe-change",
    "conflicting-sources",
    "fdc-timeout",
    "insufficient-evidence",
    "history-mismatch",
)


def _authorized_entities(scenario: Any) -> frozenset[str]:
    case = scenario.case
    return frozenset(
        {case.case_id, *case.lot_ids, *case.tool_ids, *case.recipe_ids}
    )


class ScopeCapturingAdapter(MockPlatformAdapter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context_request: CaseContextRequest | None = None

    async def get_case_context(self, request: CaseContextRequest):  # type: ignore[no-untyped-def]
        self.context_request = request
        return await super().get_case_context(request)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_name", EXECUTABLE_SCENARIOS)
async def test_workflow_calls_only_authorized_typed_sources(scenario_name: str) -> None:
    scenario = load_scenario(FIXTURES / f"{scenario_name}.json")
    adapter = ScopeCapturingAdapter(scenario, clock=lambda: NOW)
    observed: list[tuple[str, ToolResult[Any]]] = []

    async def observe(tool_id: str, result: ToolResult[Any]) -> None:
        observed.append((tool_id, result))

    collection = await YieldDropWorkflow(adapter, tool_observer=observe).collect(
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=scenario.permission_profile.permissions,
        authorized_entity_ids=_authorized_entities(scenario),
        case_id=scenario.case.case_id,
        case_version=scenario.case.case_version,
    )

    assert collection.context.case == scenario.case
    assert {result.tool_id for result in collection.results} == set(scenario.tool_results)
    assert [tool_id for tool_id, _ in observed] == [
        result.tool_id for result in collection.results
    ]
    assert set(collection.skipped_sources).isdisjoint(scenario.tool_results)
    assert adapter.context_request is not None
    assert adapter.context_request.scope.authorized_entity_ids == _authorized_entities(
        scenario
    )


@pytest.mark.asyncio
async def test_workflow_rejects_case_related_entities_outside_verified_scope() -> None:
    scenario = load_scenario(FIXTURES / "pressure-drift-success.json")

    with pytest.raises(PermissionError, match="CASE_RELATED_ENTITY_ACCESS_DENIED"):
        await YieldDropWorkflow(
            MockPlatformAdapter(scenario, clock=lambda: NOW)
        ).collect(
            tenant_id="synthetic-tenant",
            user_id="synthetic-engineer",
            permissions=scenario.permission_profile.permissions,
            authorized_entity_ids=frozenset({scenario.case.case_id}),
            case_id=scenario.case.case_id,
            case_version=scenario.case.case_version,
        )


@pytest.mark.asyncio
async def test_workflow_preserves_failed_source_as_a_gap() -> None:
    scenario = load_scenario(FIXTURES / "fdc-timeout.json")
    collection = await YieldDropWorkflow(
        MockPlatformAdapter(scenario, clock=lambda: NOW)
    ).collect(
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=scenario.permission_profile.permissions,
        authorized_entity_ids=_authorized_entities(scenario),
        case_id=scenario.case.case_id,
        case_version=scenario.case.case_version,
    )

    failed = next(result for result in collection.results if result.tool_id == "get_fdc_evidence")
    assert failed.data is None
    assert failed.error is not None
    assert failed.error.code == "TIMEOUT"
    assert failed.quality.completeness == 0.0
