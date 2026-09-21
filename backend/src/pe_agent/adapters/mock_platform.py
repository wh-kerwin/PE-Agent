from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from pe_agent.domain import (
    Case,
    CaseContext,
    CaseContextRequest,
    DomainModel,
    FdcEvidence,
    FdcRequest,
    HistoricalCaseEvidence,
    LotYieldRequest,
    RecipeEvidence,
    RecipeRequest,
    SimilarCasesRequest,
    SpcEvidence,
    SpcRequest,
    ToolCall,
    ToolError,
    ToolErrorCode,
    ToolEventEvidence,
    ToolEventsRequest,
    ToolQuality,
    ToolResult,
    ToolSource,
    ToolStatus,
    YieldEvidence,
)
from pe_agent.ports import PlatformDataPort
from pe_agent.testing.scenarios import Scenario, load_scenario

Clock = Callable[[], datetime]
EvidencePayload = TypeVar("EvidencePayload", bound=DomainModel)


class MockPlatformAdapter(PlatformDataPort):
    """Deterministic, fixture-backed implementation of the read-only platform port."""

    adapter_version = "mock-platform-v1"

    def __init__(self, scenario: Scenario, *, clock: Clock | None = None) -> None:
        self._scenario = scenario
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_file(cls, path: str, *, clock: Clock | None = None) -> MockPlatformAdapter:
        from pathlib import Path

        return cls(load_scenario(Path(path)), clock=clock)

    async def get_case(self, case_id: str, case_version: str) -> Case:
        fixture_case = self._scenario.case
        if "case.read" not in self._scenario.permission_profile.permissions:
            raise PermissionError("CASE_ACCESS_DENIED")
        if fixture_case.case_id != case_id:
            raise LookupError("CASE_NOT_FOUND")
        if fixture_case.case_version != case_version:
            raise ValueError("CASE_VERSION_CONFLICT")
        return fixture_case

    async def get_case_context(self, request: CaseContextRequest) -> CaseContext:
        if request.case_id not in request.scope.authorized_entity_ids:
            raise PermissionError("CASE_ACCESS_DENIED")
        case = await self.get_case(request.case_id, request.case_version)
        return CaseContext(case=case, source_ids=(f"SYN-CASE:{case.case_id}",))

    async def get_lot_yield(
        self, request: LotYieldRequest
    ) -> ToolResult[YieldEvidence]:
        self._authorize_entity(request.scope.authorized_entity_ids, request.lot_id)
        if request.process_step != self._scenario.case.process_step:
            raise PermissionError("ENTITY_ACCESS_DENIED")
        return await self._typed_result(
            "get_lot_yield",
            request.scope.permissions,
            lambda data, source_ids: YieldEvidence(
                observed_percent=data["observedPercent"],
                baseline_percent=data["baselinePercent"],
                source_ids=source_ids,
            ),
        )

    async def get_tool_events(
        self, request: ToolEventsRequest
    ) -> ToolResult[ToolEventEvidence]:
        self._authorize_entity(request.scope.authorized_entity_ids, request.tool_id)
        return await self._typed_result(
            "get_tool_events",
            request.scope.permissions,
            lambda data, source_ids: ToolEventEvidence(
                event_ids=tuple(data.get("eventIds", ())),
                source_ids=source_ids,
            ),
        )

    async def get_recipe_snapshot(
        self, request: RecipeRequest
    ) -> ToolResult[RecipeEvidence]:
        self._authorize_entity(request.scope.authorized_entity_ids, request.recipe_id)
        return await self._typed_result(
            "get_recipe_snapshot",
            request.scope.permissions,
            lambda data, source_ids: RecipeEvidence(
                recipe_id=str(data.get("recipeId", request.recipe_id)),
                source_ids=source_ids,
            ),
        )

    async def get_spc_evidence(self, request: SpcRequest) -> ToolResult[SpcEvidence]:
        self._authorize_entity(request.scope.authorized_entity_ids, request.tool_id)
        return await self._typed_result(
            "get_spc_evidence",
            request.scope.permissions,
            lambda data, source_ids: SpcEvidence(
                parameter=data["parameter"],
                rule_violation=data["ruleViolation"],
                unit=data.get("unit"),
                source_ids=source_ids,
            ),
        )

    async def get_fdc_evidence(self, request: FdcRequest) -> ToolResult[FdcEvidence]:
        self._authorize_entity(request.scope.authorized_entity_ids, request.tool_id)
        return await self._typed_result(
            "get_fdc_evidence",
            request.scope.permissions,
            lambda data, source_ids: FdcEvidence(
                parameter=data["parameter"],
                drift_percent=data["driftPercent"],
                source_ids=source_ids,
            ),
        )

    async def search_similar_cases(
        self, request: SimilarCasesRequest
    ) -> ToolResult[HistoricalCaseEvidence]:
        if request.process_step != self._scenario.case.process_step:
            raise PermissionError("ENTITY_ACCESS_DENIED")
        return await self._typed_result(
            "search_similar_cases",
            request.scope.permissions,
            lambda data, source_ids: HistoricalCaseEvidence(
                case_ids=tuple(data.get("caseIds", ())),
                source_ids=source_ids,
            ),
        )

    @staticmethod
    def _authorize_entity(authorized_entity_ids: frozenset[str], entity_id: str) -> None:
        if entity_id not in authorized_entity_ids:
            raise PermissionError("ENTITY_ACCESS_DENIED")

    async def _typed_result(
        self,
        tool_id: str,
        permissions: frozenset[str],
        payload_factory: Callable[[dict[str, Any], tuple[str, ...]], EvidencePayload],
    ) -> ToolResult[EvidencePayload]:
        result = await self.execute_tool(
            ToolCall(
                tool_call_id=f"MOCK-{tool_id}",
                task_id="MOCK-TASK",
                tool_id=tool_id,
                arguments={},
                deadline_at=self._clock() + timedelta(seconds=8),
                permission_scope=permissions,
            )
        )
        payload = None
        if result.data is not None and result.source is not None:
            payload = payload_factory(result.data, result.source.record_ids)
        return ToolResult[EvidencePayload](
            tool_call_id=result.tool_call_id,
            tool_id=result.tool_id,
            status=result.status,
            data=payload,
            source=result.source,
            quality=result.quality,
            retrieved_at=result.retrieved_at,
            evidence=result.evidence,
            error=result.error,
        )

    async def execute_tool(self, call: ToolCall) -> ToolResult[dict[str, Any]]:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return an aware timestamp")
        if now >= call.deadline_at:
            return self._failure(
                call,
                now,
                ToolErrorCode.TIMEOUT,
                "tool deadline elapsed",
                retryable=True,
            )

        fixture = self._scenario.tool_results.get(call.tool_id)
        if fixture is None:
            return self._failure(
                call,
                now,
                ToolErrorCode.INVALID_ARGUMENTS,
                "tool is not present in the scenario",
                retryable=False,
            )

        granted = self._scenario.permission_profile.permissions & call.permission_scope
        if fixture.required_permission not in granted:
            return self._failure(
                call,
                now,
                ToolErrorCode.PERMISSION_DENIED,
                "permission denied",
                retryable=False,
            )

        source = (
            ToolSource(
                system=fixture.source.system,
                record_ids=fixture.source.record_ids,
                adapter_version=self.adapter_version,
            )
            if fixture.source is not None
            else None
        )
        error = (
            ToolError(
                code=fixture.error_code,
                message=self._error_message(fixture.error_code),
                retryable=fixture.retryable,
            )
            if fixture.error_code is not None
            else None
        )
        return ToolResult[dict[str, Any]](
            tool_call_id=call.tool_call_id,
            tool_id=call.tool_id,
            status=fixture.status,
            data=fixture.data,
            source=source,
            quality=ToolQuality(
                completeness=fixture.completeness,
                warnings=fixture.warnings,
            ),
            retrieved_at=now,
            evidence=fixture.evidence,
            error=error,
        )

    @staticmethod
    def _error_message(code: ToolErrorCode) -> str:
        messages = {
            ToolErrorCode.INVALID_ARGUMENTS: "invalid tool arguments",
            ToolErrorCode.PERMISSION_DENIED: "permission denied",
            ToolErrorCode.VERSION_CONFLICT: "case version conflict",
            ToolErrorCode.TIMEOUT: "tool timed out",
            ToolErrorCode.UNAVAILABLE: "source unavailable",
            ToolErrorCode.NOT_FOUND: "source record not found",
        }
        return messages[code]

    @staticmethod
    def _failure(
        call: ToolCall,
        retrieved_at: datetime,
        code: ToolErrorCode,
        message: str,
        *,
        retryable: bool,
    ) -> ToolResult[dict[str, Any]]:
        return ToolResult[dict[str, Any]](
            tool_call_id=call.tool_call_id,
            tool_id=call.tool_id,
            status=ToolStatus.FAILED,
            data=None,
            source=None,
            quality=ToolQuality(completeness=0.0, warnings=(message,)),
            retrieved_at=retrieved_at,
            error=ToolError(code=code, message=message, retryable=retryable),
        )
