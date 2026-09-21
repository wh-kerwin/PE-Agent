from __future__ import annotations

from typing import Protocol

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


class PlatformDataPort(Protocol):
    @property
    def adapter_version(self) -> str: ...

    async def get_case_context(self, request: CaseContextRequest) -> CaseContext: ...

    async def get_lot_yield(
        self, request: LotYieldRequest
    ) -> ToolResult[YieldEvidence]: ...

    async def get_tool_events(
        self, request: ToolEventsRequest
    ) -> ToolResult[ToolEventEvidence]: ...

    async def get_recipe_snapshot(
        self, request: RecipeRequest
    ) -> ToolResult[RecipeEvidence]: ...

    async def get_spc_evidence(self, request: SpcRequest) -> ToolResult[SpcEvidence]: ...

    async def get_fdc_evidence(self, request: FdcRequest) -> ToolResult[FdcEvidence]: ...

    async def search_similar_cases(
        self, request: SimilarCasesRequest
    ) -> ToolResult[HistoricalCaseEvidence]: ...


PlatformPort = PlatformDataPort
