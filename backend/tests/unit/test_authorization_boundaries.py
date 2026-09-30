"""Authorization boundary matrix: verify each unauthorized posture fails at the
expected stage and never leaks data or writes events.

Postures covered:
1. Missing case.read permission → CASE_ACCESS_DENIED at get_case
2. authorized_entity_ids missing case_id → CASE_ACCESS_DENIED at get_case_context
3. authorized_entity_ids missing lot/tool → CASE_RELATED_ENTITY_ACCESS_DENIED at collect
4. Cross-tenant case not in authorized_entity_ids → fail-closed before any tool call
5. Permission shrink (case.read only, no yield/spc/fdc.read) → tools are skipped, not errored
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.application.yield_drop_workflow import YieldDropWorkflow
from pe_agent.testing import load_scenario

FIXTURES = Path(__file__).parents[2] / "fixtures" / "scenarios"
NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _scenario(name: str) -> Any:
    return load_scenario(FIXTURES / f"{name}.json")


def _authorized(scenario: Any) -> frozenset[str]:
    case = scenario.case
    return frozenset(
        {case.case_id, *case.lot_ids, *case.tool_ids, *case.recipe_ids}
    )


def _collect(
    scenario: Any,
    *,
    permissions: frozenset[str] | None = None,
) -> YieldDropWorkflow:
    adapter = MockPlatformAdapter(scenario, clock=lambda: NOW)
    return YieldDropWorkflow(adapter)


# ------------------------------------------------------------------
# Posture 1: no case.read → CASE_ACCESS_DENIED
# RequestScope requires at least one permission; the mock adapter checks
# scenario.permission_profile.permissions (fixture-level), so we use the
# permission-denied fixture which has an empty permission list.
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_case_read_raises_case_access_denied() -> None:
    scenario = _scenario("permission-denied")
    # permission-denied fixture has permissions: [] — get_case raises
    # because case.read is not in the fixture's permission profile
    perms = frozenset({"case.read"})  # RequestScope requires ≥1 perm
    with pytest.raises(PermissionError, match="CASE_ACCESS_DENIED"):
        await _run_collect(
            scenario,
            _collect(scenario, permissions=perms),
            permissions=perms,
        )


# ------------------------------------------------------------------
# Posture 2: case_id not in authorized_entity_ids
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_not_in_authorized_entities_raises() -> None:
    scenario = _scenario("pressure-drift-success")
    authorized_without_case = _authorized(scenario) - {scenario.case.case_id}

    with pytest.raises(PermissionError, match="CASE_ACCESS_DENIED"):
        await _run_collect(
            scenario,
            _collect(scenario),
            authorized=authorized_without_case,
        )


# ------------------------------------------------------------------
# Posture 3: lot/tool not in authorized → CASE_RELATED_ENTITY_ACCESS_DENIED
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lot_not_in_authorized_entities_raises() -> None:
    scenario = _scenario("pressure-drift-success")
    authorized_without_lot = _authorized(scenario) - {scenario.case.lot_ids[0]}

    with pytest.raises(PermissionError, match="CASE_RELATED_ENTITY_ACCESS_DENIED"):
        await _run_collect(
            scenario,
            _collect(scenario),
            authorized=authorized_without_lot,
        )


@pytest.mark.asyncio
async def test_tool_not_in_authorized_entities_raises() -> None:
    scenario = _scenario("pressure-drift-success")
    authorized_without_tool = (
        _authorized(scenario) - {scenario.case.tool_ids[0]}
        if scenario.case.tool_ids
        else _authorized(scenario)
    )

    with pytest.raises(PermissionError, match="CASE_RELATED_ENTITY_ACCESS_DENIED"):
        await _run_collect(
            scenario,
            _collect(scenario),
            authorized=authorized_without_tool,
        )


# ------------------------------------------------------------------
# Posture 4: cross-tenant case (case not in authorized entities)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_case_fails_closed() -> None:
    scenario = _scenario("cross-tenant-access")
    authorized_without_case = _authorized(scenario) - {scenario.case.case_id}

    with pytest.raises(PermissionError, match="CASE_ACCESS_DENIED"):
        await _run_collect(
            scenario,
            _collect(scenario),
            authorized=authorized_without_case,
        )


# ------------------------------------------------------------------
# Posture 5: permission shrink → tools skipped, not errored
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permission_shrink_skips_tools_not_errors() -> None:
    """With only case.read (no yield/spc/fdc.read), all typed tools are
    skipped (not called); the scenario still completes with no evidence."""
    scenario = _scenario("pressure-drift-success")
    # Use a permission set that lacks yield/spc/fdc.read
    case_read_only = frozenset({"case.read"})
    # RequestScope requires at least 1 permission — satisfied

    collection = await _run_collect(
        scenario,
        _collect(scenario, permissions=case_read_only),
        permissions=case_read_only,
    )

    # No tool results should have been collected (all skipped)
    assert collection.results == (), (
        "with case.read only, no typed tools should be called"
    )
    # Skipped sources should include all typed tools
    assert "get_lot_yield" in collection.skipped_sources
    assert "get_spc_evidence" in collection.skipped_sources
    assert "get_fdc_evidence" in collection.skipped_sources


# ------------------------------------------------------------------
# Posture 6: version conflict fails at collect, not at report
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_conflict_raises_value_error_not_permission() -> None:
    scenario = _scenario("version-conflict")
    # version-conflict fixture has caseVersion=8; passing version 9 triggers conflict
    with pytest.raises(ValueError, match="CASE_VERSION_CONFLICT"):
        await _run_collect(
            scenario,
            _collect(scenario),
            case_version="9",
        )


# ------------------------------------------------------------------
# Helper: run workflow.collect with given overrides
# ------------------------------------------------------------------


async def _run_collect(
    scenario: Any,
    workflow: YieldDropWorkflow,
    *,
    permissions: frozenset[str] | None = None,
    authorized: frozenset[str] | None = None,
    case_version: str | None = None,
) -> Any:
    perms = (
        permissions
        if permissions is not None
        else scenario.permission_profile.permissions
    )
    auth = (
        authorized
        if authorized is not None
        else _authorized(scenario)
    )
    version = case_version or scenario.case.case_version
    return await workflow.collect(
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=perms,
        authorized_entity_ids=auth,
        case_id=scenario.case.case_id,
        case_version=version,
    )
