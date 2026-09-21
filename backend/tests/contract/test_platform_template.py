from __future__ import annotations

import ast
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pe_agent.adapters.platform.template import (
    ADAPTER_NOT_CONFIGURED,
    AdapterNotConfiguredError,
    CustomerPlatformAdapter,
)
from pe_agent.domain import (
    CaseContextRequest,
    FdcRequest,
    LotYieldRequest,
    RecipeRequest,
    RequestScope,
    SimilarCasesRequest,
    SpcRequest,
    ToolEventsRequest,
)
from pe_agent.ports.platform import PlatformPort

NOW = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
SCOPE = RequestScope(
    tenant_id="synthetic-tenant",
    user_id="synthetic-engineer",
    permissions=frozenset(
        {
            "case.read",
            "yield.read",
            "equipment.read",
            "recipe.read",
            "spc.read",
            "fdc.read",
            "casebook.read",
        }
    ),
    authorized_entity_ids=frozenset(
        {"SYN-CASE", "SYN-LOT", "SYN-TOOL", "SYN-RECIPE"}
    ),
)


def _requests() -> tuple[tuple[str, Callable[[], Awaitable[Any]]], ...]:
    adapter = CustomerPlatformAdapter()
    window = {"start_at": NOW - timedelta(hours=1), "end_at": NOW}
    return (
        (
            "get_case_context",
            lambda: adapter.get_case_context(
                CaseContextRequest(scope=SCOPE, case_id="SYN-CASE", case_version="1")
            ),
        ),
        (
            "get_lot_yield",
            lambda: adapter.get_lot_yield(
                LotYieldRequest(
                    scope=SCOPE,
                    lot_id="SYN-LOT",
                    process_step="SYNTHETIC_ETCH",
                    **window,
                )
            ),
        ),
        (
            "get_tool_events",
            lambda: adapter.get_tool_events(
                ToolEventsRequest(scope=SCOPE, tool_id="SYN-TOOL", **window)
            ),
        ),
        (
            "get_recipe_snapshot",
            lambda: adapter.get_recipe_snapshot(
                RecipeRequest(scope=SCOPE, recipe_id="SYN-RECIPE", effective_at=NOW)
            ),
        ),
        (
            "get_spc_evidence",
            lambda: adapter.get_spc_evidence(
                SpcRequest(scope=SCOPE, tool_id="SYN-TOOL", **window)
            ),
        ),
        (
            "get_fdc_evidence",
            lambda: adapter.get_fdc_evidence(
                FdcRequest(scope=SCOPE, tool_id="SYN-TOOL", **window)
            ),
        ),
        (
            "search_similar_cases",
            lambda: adapter.search_similar_cases(
                SimilarCasesRequest(
                    scope=SCOPE,
                    case_type="YIELD_DROP",
                    process_step="SYNTHETIC_ETCH",
                )
            ),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("operation", "invoke"), _requests())
async def test_template_fails_before_io(
    operation: str,
    invoke: Callable[[], Awaitable[Any]],
) -> None:
    with pytest.raises(AdapterNotConfiguredError, match=ADAPTER_NOT_CONFIGURED) as raised:
        await invoke()

    assert raised.value.code == ADAPTER_NOT_CONFIGURED
    assert raised.value.operation == operation


def test_template_satisfies_platform_port() -> None:
    adapter: PlatformPort = CustomerPlatformAdapter()
    assert adapter.adapter_version.endswith("unconfigured")


def test_template_never_imports_mock_or_fixture_modules() -> None:
    source_path = Path(__file__).parents[2] / "src/pe_agent/adapters/platform/template.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )

    assert not any("mock" in module.lower() or "fixture" in module.lower() for module in imported)
