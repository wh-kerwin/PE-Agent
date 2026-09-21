from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.domain import (
    LotYieldRequest,
    RequestScope,
    ToolCall,
    ToolErrorCode,
    ToolStatus,
)
from pe_agent.testing import exercise_platform_contract, load_scenario

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "scenarios"
NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _adapter(name: str) -> MockPlatformAdapter:
    scenario = load_scenario(FIXTURE_DIR / f"{name}.json")
    return MockPlatformAdapter(scenario, clock=lambda: NOW)


def _call(tool_id: str, *, deadline_at: datetime | None = None) -> ToolCall:
    return ToolCall(
        tool_call_id="SYN-CALL-1",
        task_id="SYN-TASK-1",
        tool_id=tool_id,
        arguments={},
        deadline_at=deadline_at or NOW + timedelta(seconds=8),
        permission_scope=frozenset({"case.read", "yield.read", "spc.read", "fdc.read"}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario_name",
    [
        "pressure-drift-success",
        "recipe-change",
        "conflicting-sources",
        "fdc-timeout",
        "insufficient-evidence",
        "history-mismatch",
    ],
)
async def test_mock_platform_passes_reusable_contract_support(
    scenario_name: str,
) -> None:
    scenario = load_scenario(FIXTURE_DIR / f"{scenario_name}.json")
    adapter = MockPlatformAdapter(scenario, clock=lambda: NOW)

    results = await exercise_platform_contract(adapter, scenario, now=NOW)

    assert len(results) == len(scenario.tool_results)
    assert {result.retrieved_at for result in results} <= {NOW}


@pytest.mark.asyncio
async def test_fixture_timeout_is_deterministic() -> None:
    result = await _adapter("fdc-timeout").execute_tool(_call("get_fdc_evidence"))

    assert result.status is ToolStatus.FAILED
    assert result.error is not None
    assert result.error.code is ToolErrorCode.TIMEOUT
    assert result.error.retryable


@pytest.mark.asyncio
async def test_elapsed_deadline_wins_over_fixture_result() -> None:
    result = await _adapter("pressure-drift-success").execute_tool(
        _call("get_lot_yield", deadline_at=NOW)
    )

    assert result.status is ToolStatus.FAILED
    assert result.error is not None
    assert result.error.code is ToolErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_permission_denial_is_deterministic() -> None:
    adapter = _adapter("pressure-drift-success")
    call = ToolCall(
        tool_call_id="SYN-CALL-DENIED",
        task_id="SYN-TASK",
        tool_id="get_fdc_evidence",
        arguments={},
        deadline_at=NOW + timedelta(seconds=8),
        permission_scope=frozenset({"case.read"}),
    )

    result = await adapter.execute_tool(call)

    assert result.status is ToolStatus.FAILED
    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED
    assert not result.error.retryable


@pytest.mark.asyncio
async def test_typed_reads_enforce_entity_scope() -> None:
    adapter = _adapter("pressure-drift-success")
    scope = RequestScope(
        tenant_id="synthetic-tenant",
        user_id="synthetic-user",
        permissions=frozenset({"case.read", "yield.read"}),
        authorized_entity_ids=frozenset({"SYN-CASE-PRESSURE-001"}),
    )

    with pytest.raises(PermissionError, match="ENTITY_ACCESS_DENIED"):
        await adapter.get_lot_yield(
            LotYieldRequest(
                scope=scope,
                lot_id="SYN-LOT-001",
                process_step="SYNTHETIC_ETCH",
                start_at=NOW - timedelta(hours=1),
                end_at=NOW,
            )
        )


@pytest.mark.asyncio
async def test_case_version_conflict_is_deterministic() -> None:
    adapter = _adapter("version-conflict")

    with pytest.raises(ValueError, match="CASE_VERSION_CONFLICT"):
        await adapter.get_case("SYN-CASE-VERSION", "7")


@pytest.mark.asyncio
async def test_case_access_denial_is_deterministic() -> None:
    adapter = _adapter("permission-denied")

    with pytest.raises(PermissionError, match="CASE_ACCESS_DENIED"):
        await adapter.get_case("SYN-CASE-DENIED", "1")
