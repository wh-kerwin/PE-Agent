from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from pe_agent.domain.base import DomainModel, NonEmptyStr
from pe_agent.domain.enums import ArchiveStatus, ReviewStatus, TaskStatus

_RUNNING = {
    TaskStatus.CREATED,
    TaskStatus.CONTEXT_LOADING,
    TaskStatus.INVESTIGATING,
    TaskStatus.ANALYZING,
    TaskStatus.GENERATING_REPORT,
}
_TERMINAL = {
    TaskStatus.COMPLETED,
    TaskStatus.PARTIAL_RESULT,
    TaskStatus.FAILED,
    TaskStatus.TIMEOUT,
    TaskStatus.CANCELLED,
}


class AnalysisTask(DomainModel):
    task_id: NonEmptyStr
    case_id: NonEmptyStr
    case_version: NonEmptyStr
    status: TaskStatus
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    warnings: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_lifecycle(self) -> AnalysisTask:
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt cannot precede createdAt")
        if self.status in _RUNNING and self.completed_at is not None:
            raise ValueError("running tasks cannot have completedAt")
        if self.status in _TERMINAL and self.completed_at is None:
            raise ValueError("terminal tasks require completedAt")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("completedAt cannot precede createdAt")
        return self


class EngineerReview(DomainModel):
    task_id: NonEmptyStr
    report_version: int = Field(strict=True, ge=1)
    revision: int = Field(strict=True, ge=1)
    status: ReviewStatus
    helpful: bool | None = None
    confirmed_hypothesis_id: NonEmptyStr | None = None
    actual_root_cause: NonEmptyStr | None = None
    comment: NonEmptyStr | None = None
    reviewed_at: datetime

    @model_validator(mode="after")
    def require_a_human_decision(self) -> EngineerReview:
        if self.status is ReviewStatus.NOT_REVIEWED:
            raise ValueError("persisted reviews must contain an engineer decision")
        if self.status is ReviewStatus.CONFIRMED and self.confirmed_hypothesis_id is None:
            raise ValueError("confirmed reviews require confirmedHypothesisId")
        if self.status is ReviewStatus.CORRECTED and self.actual_root_cause is None:
            raise ValueError("corrected reviews require actualRootCause")
        return self


class CaseBookArchive(DomainModel):
    archive_id: NonEmptyStr
    task_id: NonEmptyStr
    review_revision: int = Field(strict=True, ge=1)
    status: ArchiveStatus
    archived_at: datetime | None = None
    error: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_result(self) -> CaseBookArchive:
        if self.status is ArchiveStatus.ARCHIVED and self.archived_at is None:
            raise ValueError("archived results require archivedAt")
        if self.status is ArchiveStatus.FAILED and self.error is None:
            raise ValueError("failed archives require an error")
        return self
