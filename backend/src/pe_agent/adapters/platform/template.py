"""Fail-closed platform adapter template for customer-managed integrations."""

from __future__ import annotations

from typing import Final, NoReturn

from pe_agent.domain import (
    CaseContext,
    CaseContextRequest,
    FdcEvidence,
    FdcRequest,
    HistoricalCaseEvidence,
    LotYieldRequest,
    RecipeEvidence,
    RecipeRequest,
    SimilarCasesRequest,
    SpcEvidence,
    SpcRequest,
    ToolEventEvidence,
    ToolEventsRequest,
    ToolResult,
    YieldEvidence,
)
from pe_agent.ports.platform import PlatformPort

ADAPTER_NOT_CONFIGURED: Final = "ADAPTER_NOT_CONFIGURED"


class AdapterNotConfiguredError(RuntimeError):
    code: Final = ADAPTER_NOT_CONFIGURED

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"{ADAPTER_NOT_CONFIGURED}: {operation}")


class CustomerPlatformAdapter(PlatformPort):
    adapter_version: Final = "customer-platform-template-unconfigured"

    def __init__(self, *, configured: bool = False) -> None:
        if configured:
            raise AdapterNotConfiguredError("constructor")

    async def get_case_context(self, request: CaseContextRequest) -> CaseContext:
        del request
        self._not_configured("get_case_context")

    async def get_lot_yield(
        self, request: LotYieldRequest
    ) -> ToolResult[YieldEvidence]:
        del request
        self._not_configured("get_lot_yield")

    async def get_tool_events(
        self, request: ToolEventsRequest
    ) -> ToolResult[ToolEventEvidence]:
        del request
        self._not_configured("get_tool_events")

    async def get_recipe_snapshot(
        self, request: RecipeRequest
    ) -> ToolResult[RecipeEvidence]:
        del request
        self._not_configured("get_recipe_snapshot")

    async def get_spc_evidence(self, request: SpcRequest) -> ToolResult[SpcEvidence]:
        del request
        self._not_configured("get_spc_evidence")

    async def get_fdc_evidence(self, request: FdcRequest) -> ToolResult[FdcEvidence]:
        del request
        self._not_configured("get_fdc_evidence")

    async def search_similar_cases(
        self, request: SimilarCasesRequest
    ) -> ToolResult[HistoricalCaseEvidence]:
        del request
        self._not_configured("search_similar_cases")

    @staticmethod
    def _not_configured(operation: str) -> NoReturn:
        raise AdapterNotConfiguredError(operation)
