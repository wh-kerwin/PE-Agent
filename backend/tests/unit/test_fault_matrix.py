"""Fault matrix: assert each scenario fixture produces its declared outcome.

Covers COMPLETED / PARTIAL_RESULT / FAILED / CASE_VERSION_CONFLICT /
CASE_ACCESS_DENIED across all synthetic scenario fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.application.reporting import compose_report
from pe_agent.application.yield_drop_workflow import YieldDropWorkflow
from pe_agent.domain import ReportInput, TaskStatus
from pe_agent.testing import load_scenario

FIXTURES = Path(__file__).parents[2] / "fixtures" / "scenarios"
NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)

# scenario name → expected terminal status as reported by compose_report
# (scenarios that raise during collect are skipped here and verified by
# the workflow-level test below)
SCENARIO_COMPOSE_OUTCOMES: dict[str, TaskStatus] = {
    "pressure-drift-success": TaskStatus.COMPLETED,
    "recipe-change": TaskStatus.COMPLETED,
    "conflicting-sources": TaskStatus.PARTIAL_RESULT,
    "fdc-timeout": TaskStatus.PARTIAL_RESULT,
    "history-mismatch": TaskStatus.PARTIAL_RESULT,
    "multi-source-timeout": TaskStatus.PARTIAL_RESULT,
    "insufficient-evidence": TaskStatus.FAILED,
}

SCENARIO_COMPOSE_OUTCOMES: dict[str, TaskStatus] = {
    "pressure-drift-success": TaskStatus.COMPLETED,
    "recipe-change": TaskStatus.COMPLETED,
    "conflicting-sources": TaskStatus.PARTIAL_RESULT,
    "fdc-timeout": TaskStatus.PARTIAL_RESULT,
    "history-mismatch": TaskStatus.PARTIAL_RESULT,
    "multi-source-timeout": TaskStatus.PARTIAL_RESULT,
}

# Scenarios where collect raises — verified at the workflow level
WORKFLOW_RAISING: dict[str, tuple[str, str]] = {
    # scenario_name → (expected_exception_message, case_version_override)
    "permission-denied": ("CASE_ACCESS_DENIED", None),
    "version-conflict": ("CASE_VERSION_CONFLICT", "9"),
}


def _authorized(scenario: Any) -> frozenset[str]:
    case = scenario.case
    return frozenset(
        {case.case_id, *case.lot_ids, *case.tool_ids, *case.recipe_ids}
    )


def _all_scenario_names() -> list[str]:
    return sorted(f.stem for f in FIXTURES.glob("*.json"))


def _scenario_list() -> list[str]:
    return [
        name for name in _all_scenario_names()
        if name in SCENARIO_COMPOSE_OUTCOMES
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_name", _scenario_list())
async def test_scenario_produces_expected_compose_outcome(
    scenario_name: str,
) -> None:
    scenario = load_scenario(FIXTURES / f"{scenario_name}.json")
    expected = SCENARIO_COMPOSE_OUTCOMES[scenario_name]
    adapter = MockPlatformAdapter(scenario, clock=lambda: NOW)
    workflow = YieldDropWorkflow(adapter)
    collection = await workflow.collect(
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=scenario.permission_profile.permissions,
        authorized_entity_ids=_authorized(scenario),
        case_id=scenario.case.case_id,
        case_version=scenario.case.case_version,
    )

    report_input = ReportInput(
        task_id=f"ANA-{scenario.name}",
        report_version=1,
        context=collection.context,
        results=collection.results,
        skipped_sources=collection.skipped_sources,
        authorized_entity_ids=_authorized(scenario),
        generated_at=NOW,
        requested_model="jev-1.13.0",
        resolved_model="jev-1.13.0",
        question_set_version="yield-drop-jev-v1.0.0",
        decision=None,
    )
    outcome = compose_report(report_input)
    assert outcome.validation_errors == (), f"{scenario_name}: {outcome.validation_errors}"

    if expected is TaskStatus.COMPLETED:
        assert outcome.report is not None
    elif expected is TaskStatus.PARTIAL_RESULT:
        assert outcome.report is not None
        assert len(outcome.report["uncertainties"]) > 0, (
            f"{scenario_name}: expected at least one uncertainty"
        )


@pytest.mark.asyncio
async def test_insufficient_evidence_compose_fails_without_report() -> None:
    """insufficient-evidence: all sources FAILED, compose_report returns FAILED with no report."""
    scenario = load_scenario(FIXTURES / "insufficient-evidence.json")
    adapter = MockPlatformAdapter(scenario, clock=lambda: NOW)
    workflow = YieldDropWorkflow(adapter)
    collection = await workflow.collect(
        tenant_id="synthetic-tenant",
        user_id="synthetic-engineer",
        permissions=scenario.permission_profile.permissions,
        authorized_entity_ids=_authorized(scenario),
        case_id=scenario.case.case_id,
        case_version=scenario.case.case_version,
    )
    report_input = ReportInput(
        task_id="ANA-insufficient-evidence",
        report_version=1,
        context=collection.context,
        results=collection.results,
        skipped_sources=collection.skipped_sources,
        authorized_entity_ids=_authorized(scenario),
        generated_at=NOW,
        requested_model="jev-1.13.0",
        resolved_model="jev-1.13.0",
        question_set_version="yield-drop-jev-v1.0.0",
        decision=None,
    )
    outcome = compose_report(report_input)
    assert outcome.terminal_status is TaskStatus.FAILED
    assert outcome.report is None, "insufficient-evidence must not produce a report"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario_name",
    [name for name in WORKFLOW_RAISING],
)
async def test_workflow_raises_for_denied_scenarios(
    scenario_name: str,
) -> None:
    scenario = load_scenario(FIXTURES / f"{scenario_name}.json")
    expected_msg, version_override = WORKFLOW_RAISING[scenario_name]
    case_version = version_override or scenario.case.case_version
    adapter = MockPlatformAdapter(scenario, clock=lambda: NOW)
    workflow = YieldDropWorkflow(adapter)
    permissions = scenario.permission_profile.permissions

    # RequestScope requires at least 1 permission; use case.read for the
    # permission-denied scenario (fixture has empty permissions list)
    if not permissions:
        permissions = frozenset({"case.read"})

    if expected_msg == "CASE_ACCESS_DENIED":
        with pytest.raises(PermissionError, match=expected_msg):
            await workflow.collect(
                tenant_id="synthetic-tenant",
                user_id="synthetic-engineer",
                permissions=permissions,
                authorized_entity_ids=_authorized(scenario),
                case_id=scenario.case.case_id,
                case_version=case_version,
            )
    else:
        with pytest.raises(ValueError, match=expected_msg):
            await workflow.collect(
                tenant_id="synthetic-tenant",
                user_id="synthetic-engineer",
                permissions=permissions,
                authorized_entity_ids=_authorized(scenario),
                case_id=scenario.case.case_id,
                case_version=case_version,
            )


@pytest.mark.asyncio
async def test_cross_tenant_unauthorized_entity_raises() -> None:
    """A scenario whose case is not in authorized_entity_ids must fail-closed."""
    scenario = load_scenario(FIXTURES / "cross-tenant-access.json")
    adapter = MockPlatformAdapter(scenario, clock=lambda: NOW)
    workflow = YieldDropWorkflow(adapter)
    authorized_without_case = _authorized(scenario) - {scenario.case.case_id}

    with pytest.raises(PermissionError, match="CASE_ACCESS_DENIED"):
        await workflow.collect(
            tenant_id="synthetic-tenant",
            user_id="synthetic-engineer",
            permissions=scenario.permission_profile.permissions,
            authorized_entity_ids=authorized_without_case,
            case_id=scenario.case.case_id,
            case_version=scenario.case.case_version,
        )


# --- Fixture integrity checks ---


def test_all_scenario_files_have_valid_expected_outcome() -> None:
    valid = {
        "COMPLETED", "PARTIAL_RESULT", "FAILED",
        "CASE_VERSION_CONFLICT", "CASE_ACCESS_DENIED",
    }
    for name in _all_scenario_names():
        scenario = load_scenario(FIXTURES / f"{name}.json")
        assert scenario.expected_outcome in valid, f"{name}: invalid expected_outcome"
        assert scenario.synthetic is True, f"{name}: must be marked synthetic"


def test_all_scenario_files_are_in_outcome_maps() -> None:
    """Every scenario fixture must appear in at least one outcome map."""
    all_names = set(_all_scenario_names())
    covered = (
        set(SCENARIO_COMPOSE_OUTCOMES)
        | set(WORKFLOW_RAISING)
        | {"cross-tenant-access", "insufficient-evidence"}  # dedicated tests
    )
    missing = all_names - covered
    assert not missing, f"scenarios not covered: {sorted(missing)}"


def test_no_scenario_fixture_has_english_observations() -> None:
    """CJK regression guard: all observation and warning strings must be Chinese."""
    for name in _all_scenario_names():
        scenario = load_scenario(FIXTURES / f"{name}.json")
        for tool_id, result in scenario.tool_results.items():
            for warning in result.warnings:
                has_cjk = any("一" <= c <= "鿿" for c in warning)
                assert has_cjk, (
                    f"scenario {name!r} tool {tool_id!r} warning is not CJK: {warning!r}"
                )
            for evidence in result.evidence:
                has_cjk = any("一" <= c <= "鿿" for c in evidence.observation)
                assert has_cjk, (
                    f"scenario {name!r} tool {tool_id!r} observation is not CJK: "
                    f"{evidence.observation!r}"
                )
