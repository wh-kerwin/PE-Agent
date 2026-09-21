from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar

from pydantic import Field, model_validator

from pe_agent.domain.base import DomainModel, NonEmptyStr
from pe_agent.domain.enums import ToolErrorCode, ToolStatus
from pe_agent.domain.evidence import Evidence

ToolData = TypeVar("ToolData")


class ToolCall(DomainModel):
    tool_call_id: NonEmptyStr
    task_id: NonEmptyStr
    tool_id: NonEmptyStr
    arguments: dict[str, Any]
    deadline_at: datetime
    permission_scope: frozenset[NonEmptyStr] = Field(min_length=1)


class ToolSource(DomainModel):
    system: NonEmptyStr
    record_ids: tuple[NonEmptyStr, ...]
    adapter_version: NonEmptyStr


class ToolQuality(DomainModel):
    completeness: float = Field(strict=True, ge=0.0, le=1.0)
    warnings: tuple[NonEmptyStr, ...] = ()


class ToolError(DomainModel):
    code: ToolErrorCode
    message: NonEmptyStr
    retryable: bool


class ToolResult[ToolData](DomainModel):
    tool_call_id: NonEmptyStr
    tool_id: NonEmptyStr
    status: ToolStatus
    data: ToolData | None
    source: ToolSource | None
    quality: ToolQuality
    retrieved_at: datetime
    evidence: tuple[Evidence, ...] = ()
    error: ToolError | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> ToolResult[ToolData]:
        if self.status is ToolStatus.SUCCEEDED:
            if self.data is None or self.source is None or self.error is not None:
                raise ValueError("SUCCEEDED requires data/source and forbids error")
            if self.quality.completeness != 1.0:
                raise ValueError("SUCCEEDED requires complete data")
        elif self.status is ToolStatus.PARTIAL:
            if self.data is None or self.source is None:
                raise ValueError("PARTIAL requires available data and source")
            if self.quality.completeness >= 1.0:
                raise ValueError("PARTIAL completeness must be below 1")
        elif self.status is ToolStatus.FAILED:
            if self.data is not None or self.error is None:
                raise ValueError("FAILED requires error and forbids data")
            if self.quality.completeness != 0.0:
                raise ValueError("FAILED requires zero completeness")
            if self.evidence:
                raise ValueError("FAILED forbids evidence")
        return self
