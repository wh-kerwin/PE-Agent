from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from pe_agent.domain.base import DomainModel, NonEmptyStr
from pe_agent.domain.case import Case, Percent


class RequestScope(DomainModel):
    tenant_id: NonEmptyStr
    user_id: NonEmptyStr
    permissions: frozenset[NonEmptyStr] = Field(min_length=1)
    authorized_entity_ids: frozenset[NonEmptyStr] = Field(min_length=1)


class CaseContextRequest(DomainModel):
    scope: RequestScope
    case_id: NonEmptyStr
    case_version: NonEmptyStr


class CaseContext(DomainModel):
    case: Case
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class WindowedRequest(DomainModel):
    scope: RequestScope
    start_at: datetime
    end_at: datetime
    limit: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def constrain_window(self) -> WindowedRequest:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        if self.end_at - self.start_at > timedelta(days=31):
            raise ValueError("time window cannot exceed 31 days")
        return self


class LotYieldRequest(WindowedRequest):
    lot_id: NonEmptyStr
    process_step: NonEmptyStr


class ToolEventsRequest(WindowedRequest):
    tool_id: NonEmptyStr


class RecipeRequest(DomainModel):
    scope: RequestScope
    recipe_id: NonEmptyStr
    effective_at: datetime


class SpcRequest(WindowedRequest):
    tool_id: NonEmptyStr


class FdcRequest(WindowedRequest):
    tool_id: NonEmptyStr


class SimilarCasesRequest(DomainModel):
    scope: RequestScope
    case_type: Literal["YIELD_DROP"]
    process_step: NonEmptyStr
    limit: int = Field(default=10, ge=1, le=100)


class YieldEvidence(DomainModel):
    observed_percent: Percent
    baseline_percent: Percent
    unit: Literal["percent"] = "percent"
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class ToolEventEvidence(DomainModel):
    event_ids: tuple[NonEmptyStr, ...]
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class RecipeEvidence(DomainModel):
    recipe_id: NonEmptyStr
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class SpcEvidence(DomainModel):
    parameter: NonEmptyStr
    rule_violation: bool
    unit: NonEmptyStr | None = None
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class FdcEvidence(DomainModel):
    parameter: NonEmptyStr
    drift_percent: Percent | None
    unit: Literal["percent"] = "percent"
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class HistoricalCaseEvidence(DomainModel):
    case_ids: tuple[NonEmptyStr, ...]
    source_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
