from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: _to_camel(value),
        populate_by_name=True,
        extra="forbid",
    )


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class CreateAnalysisRequest(ApiModel):
    case_id: str = Field(min_length=1, max_length=128)
    case_version: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=64)


class TaskAccepted(ApiModel):
    task_id: str
    case_id: str
    case_version: str
    status: str
    reused: bool
    stream_url: str


class TaskSnapshot(ApiModel):
    task_id: str
    case_id: str
    case_version: str
    status: str
    phase: str | None
    progress: int = Field(ge=0, le=100)
    review_status: str = "NOT_REVIEWED"
    warnings: list[str] = Field(default_factory=list)
    latest_event_id: str
    report_version: int | None = Field(default=None, ge=1)
    report_url: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    supersedes_task_id: str | None = None
    versions: dict[str, str]


class RetryRequest(ApiModel):
    idempotency_key: str = Field(min_length=1, max_length=64)


class ReviewRequest(ApiModel):
    report_version: int = Field(ge=1)
    review_status: Literal["CONFIRMED", "CORRECTED", "INCONCLUSIVE"]
    helpful: bool | None = None
    confirmed_hypothesis_id: str | None = None
    actual_root_cause: str | None = None
    comment: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=64)


class ReviewResponse(ApiModel):
    task_id: str
    report_version: int
    review_status: Literal["CONFIRMED", "CORRECTED", "INCONCLUSIVE"]
    helpful: bool | None = None
    confirmed_hypothesis_id: str | None = None
    actual_root_cause: str | None = None
    comment: str | None = None
    idempotency_key: str
    review_revision: int = Field(ge=1)
    created_at: datetime


class ArchiveRequest(ApiModel):
    review_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=64)


class ArchiveResponse(ApiModel):
    archive_id: str
    status: Literal["PENDING", "ARCHIVED", "FAILED"]
    review_revision: int = Field(ge=1)
    message: str | None = None


class ErrorBody(ApiModel):
    code: str
    message: str
    retryable: bool
    trace_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(ApiModel):
    error: ErrorBody
