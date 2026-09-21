from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, model_validator

from pe_agent.domain.base import DomainModel, NonEmptyStr
from pe_agent.domain.enums import CaseStatus, CaseType, Severity

Percent = Annotated[float, Field(strict=True, ge=0.0, le=100.0)]


class YieldSymptom(DomainModel):
    observed_yield_percent: Percent
    baseline_yield_percent: Percent

    @model_validator(mode="after")
    def observed_must_be_below_baseline(self) -> YieldSymptom:
        if self.observed_yield_percent >= self.baseline_yield_percent:
            raise ValueError("YIELD_DROP requires observed yield below baseline")
        return self

    @property
    def absolute_drop_percentage_points(self) -> float:
        """Absolute percentage-point drop, not relative percent change."""
        return round(self.baseline_yield_percent - self.observed_yield_percent, 6)


class Case(DomainModel):
    case_id: NonEmptyStr
    case_version: NonEmptyStr
    case_type: CaseType
    severity: Severity
    status: CaseStatus
    process_step: NonEmptyStr
    created_at: datetime
    lot_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    tool_ids: tuple[NonEmptyStr, ...] = ()
    recipe_ids: tuple[NonEmptyStr, ...] = ()
    symptom: YieldSymptom
    synthetic: bool

    @model_validator(mode="after")
    def require_yield_drop_case(self) -> Case:
        if self.case_type is not CaseType.YIELD_DROP:
            raise ValueError("V1 supports only YIELD_DROP cases")
        return self
