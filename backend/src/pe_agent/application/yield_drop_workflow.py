from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pe_agent.domain import (
    CaseContext,
    CaseContextRequest,
    FdcRequest,
    LotYieldRequest,
    RecipeRequest,
    RequestScope,
    SimilarCasesRequest,
    SpcRequest,
    ToolEventsRequest,
    ToolResult,
)
from pe_agent.ports import PlatformDataPort

ToolObserver = Callable[[str, ToolResult[Any]], Awaitable[None]]


@dataclass(frozen=True)
class WorkflowCollection:
    context: CaseContext
    results: tuple[ToolResult[Any], ...]
    skipped_sources: tuple[str, ...]


class YieldDropWorkflow:
    def __init__(
        self,
        platform: PlatformDataPort,
        *,
        tool_observer: ToolObserver | None = None,
    ) -> None:
        self._platform = platform
        self._tool_observer = tool_observer

    async def collect(
        self,
        *,
        tenant_id: str,
        user_id: str,
        permissions: frozenset[str],
        authorized_entity_ids: frozenset[str],
        case_id: str,
        case_version: str,
    ) -> WorkflowCollection:
        initial_scope = RequestScope(
            tenant_id=tenant_id,
            user_id=user_id,
            permissions=permissions,
            authorized_entity_ids=authorized_entity_ids,
        )
        context = await self._platform.get_case_context(
            CaseContextRequest(
                scope=initial_scope,
                case_id=case_id,
                case_version=case_version,
            )
        )
        case = context.case
        if case.case_id != case_id or case.case_version != case_version:
            raise ValueError("CASE_VERSION_CONFLICT")

        related_entities = frozenset(
            {
                case.case_id,
                *case.lot_ids,
                *case.tool_ids,
                *case.recipe_ids,
            }
        )
        unauthorized_entities = related_entities - authorized_entity_ids
        if unauthorized_entities:
            raise PermissionError("CASE_RELATED_ENTITY_ACCESS_DENIED")
        scope = initial_scope
        start_at = case.created_at - timedelta(hours=24)
        end_at = case.created_at + timedelta(hours=1)
        calls: list[
            tuple[str, Callable[[], Awaitable[ToolResult[Any]]]]
        ] = []
        skipped: list[str] = []

        if "yield.read" in permissions:
            calls.append(
                (
                    "get_lot_yield",
                    lambda: self._platform.get_lot_yield(
                        LotYieldRequest(
                            scope=scope,
                            lot_id=case.lot_ids[0],
                            process_step=case.process_step,
                            start_at=start_at,
                            end_at=end_at,
                        )
                    ),
                )
            )
        else:
            skipped.append("get_lot_yield")

        if case.tool_ids and "equipment.read" in permissions:
            calls.append(
                (
                    "get_tool_events",
                    lambda: self._platform.get_tool_events(
                        ToolEventsRequest(
                            scope=scope,
                            tool_id=case.tool_ids[0],
                            start_at=start_at,
                            end_at=end_at,
                        )
                    ),
                )
            )
        else:
            skipped.append("get_tool_events")

        if case.recipe_ids and "recipe.read" in permissions:
            calls.append(
                (
                    "get_recipe_snapshot",
                    lambda: self._platform.get_recipe_snapshot(
                        RecipeRequest(
                            scope=scope,
                            recipe_id=case.recipe_ids[0],
                            effective_at=case.created_at,
                        )
                    ),
                )
            )
        else:
            skipped.append("get_recipe_snapshot")

        if case.tool_ids and "spc.read" in permissions:
            calls.append(
                (
                    "get_spc_evidence",
                    lambda: self._platform.get_spc_evidence(
                        SpcRequest(
                            scope=scope,
                            tool_id=case.tool_ids[0],
                            start_at=start_at,
                            end_at=end_at,
                        )
                    ),
                )
            )
        else:
            skipped.append("get_spc_evidence")

        if case.tool_ids and "fdc.read" in permissions:
            calls.append(
                (
                    "get_fdc_evidence",
                    lambda: self._platform.get_fdc_evidence(
                        FdcRequest(
                            scope=scope,
                            tool_id=case.tool_ids[0],
                            start_at=start_at,
                            end_at=end_at,
                        )
                    ),
                )
            )
        else:
            skipped.append("get_fdc_evidence")

        if "casebook.read" in permissions:
            calls.append(
                (
                    "search_similar_cases",
                    lambda: self._platform.search_similar_cases(
                        SimilarCasesRequest(
                            scope=scope,
                            case_type="YIELD_DROP",
                            process_step=case.process_step,
                        )
                    ),
                )
            )
        else:
            skipped.append("search_similar_cases")

        results: list[ToolResult[Any]] = []
        for offset in range(0, len(calls), 3):
            batch = calls[offset : offset + 3]
            resolved = await asyncio.gather(*(invoke() for _, invoke in batch))
            for (tool_id, _), result in zip(batch, resolved, strict=True):
                if result.tool_id != tool_id:
                    raise ValueError("platform returned a mismatched tool result")
                results.append(result)
                if self._tool_observer is not None:
                    await self._tool_observer(tool_id, result)

        return WorkflowCollection(
            context=context,
            results=tuple(results),
            skipped_sources=tuple(skipped),
        )
