from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from pe_agent.domain import (
    Case,
    DomainModel,
    Evidence,
    FdcEvidence,
    HistoricalCaseEvidence,
    NonEmptyStr,
    RecipeEvidence,
    SpcEvidence,
    ToolErrorCode,
    ToolEventEvidence,
    ToolStatus,
    YieldEvidence,
)

ExpectedOutcome = Literal[
    "COMPLETED",
    "PARTIAL_RESULT",
    "FAILED",
    "CASE_VERSION_CONFLICT",
    "CASE_ACCESS_DENIED",
]


class PermissionProfile(DomainModel):
    name: NonEmptyStr
    permissions: frozenset[NonEmptyStr]


class FixtureToolSource(DomainModel):
    system: NonEmptyStr
    record_ids: tuple[NonEmptyStr, ...]


class FixtureToolResult(DomainModel):
    status: ToolStatus
    required_permission: NonEmptyStr
    data: dict[str, Any] | None = None
    source: FixtureToolSource | None = None
    completeness: float = Field(strict=True, ge=0.0, le=1.0)
    warnings: tuple[NonEmptyStr, ...] = ()
    error_code: ToolErrorCode | None = None
    retryable: bool = False
    evidence: tuple[Evidence, ...] = ()

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.evidence)

    @model_validator(mode="after")
    def validate_result_shape(self) -> FixtureToolResult:
        if self.status is ToolStatus.SUCCEEDED:
            if self.data is None or self.source is None or self.completeness != 1.0:
                raise ValueError("successful fixture tool results require complete data and source")
            if self.error_code is not None:
                raise ValueError("successful fixture tool results cannot contain an error")
        elif self.status is ToolStatus.PARTIAL:
            if self.data is None or self.source is None or self.completeness >= 1.0:
                raise ValueError("partial fixture tool results require incomplete data and source")
        elif self.status is ToolStatus.FAILED:
            if self.data is not None or self.error_code is None or self.completeness != 0.0:
                raise ValueError("failed fixture tool results require only an error")
        return self


class Scenario(DomainModel):
    name: NonEmptyStr
    synthetic: Literal[True]
    expected_outcome: ExpectedOutcome
    unavailable_sources: tuple[NonEmptyStr, ...]
    evidence_ids: tuple[NonEmptyStr, ...]
    permission_profile: PermissionProfile
    case: Case
    tool_results: dict[NonEmptyStr, FixtureToolResult]

    @model_validator(mode="after")
    def validate_cross_references(self) -> Scenario:
        fixture_ids = tuple(
            evidence_id
            for result in self.tool_results.values()
            for evidence_id in result.evidence_ids
        )
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("scenario evidenceIds must be unique")
        if set(fixture_ids) != set(self.evidence_ids):
            raise ValueError("scenario evidenceIds must match tool result evidenceIds")
        failed_tools = {
            tool_id
            for tool_id, result in self.tool_results.items()
            if result.status is ToolStatus.FAILED
        }
        if set(self.unavailable_sources) != failed_tools:
            raise ValueError("unavailableSources must name every and only failed tool")
        self._validate_tool_payloads()
        return self

    def _validate_tool_payloads(self) -> None:
        for tool_id, result in self.tool_results.items():
            if result.data is None or result.source is None:
                continue
            source_ids = result.source.record_ids
            data = result.data
            if tool_id == "get_lot_yield":
                YieldEvidence.model_validate(
                    {
                        "observedPercent": data.get("observedPercent"),
                        "baselinePercent": data.get("baselinePercent"),
                        "sourceIds": source_ids,
                    }
                )
            elif tool_id == "get_tool_events":
                ToolEventEvidence.model_validate(
                    {"eventIds": data.get("eventIds", ()), "sourceIds": source_ids}
                )
            elif tool_id == "get_recipe_snapshot":
                RecipeEvidence.model_validate(
                    {"recipeId": data.get("recipeId"), "sourceIds": source_ids}
                )
            elif tool_id == "get_spc_evidence":
                SpcEvidence.model_validate(
                    {
                        "parameter": data.get("parameter"),
                        "ruleViolation": data.get("ruleViolation"),
                        "unit": data.get("unit"),
                        "sourceIds": source_ids,
                    }
                )
            elif tool_id == "get_fdc_evidence":
                FdcEvidence.model_validate(
                    {
                        "parameter": data.get("parameter"),
                        "driftPercent": data.get("driftPercent"),
                        "sourceIds": source_ids,
                    }
                )
            elif tool_id == "search_similar_cases":
                HistoricalCaseEvidence.model_validate(
                    {"caseIds": tuple(data.get("caseIds", ())), "sourceIds": source_ids}
                )
            else:
                raise ValueError(f"unsupported fixture tool {tool_id}")


def load_scenario(path: Path) -> Scenario:
    """Load a strictly validated synthetic scenario from disk."""
    try:
        payload = path.read_text(encoding="utf-8")
        return Scenario.model_validate_json(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid scenario fixture {path}: {exc}") from exc
