from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AnalysisTaskModel(Base):
    __tablename__ = "ai_analysis_task"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "permission_scope_hash",
            "idempotency_key",
            name="uq_task_idempotency_scope",
        ),
        Index("ix_task_tenant_case_created", "tenant_id", "case_id", "created_at"),
        Index("ix_task_status", "status"),
        CheckConstraint(
            "status IN ('CREATED', 'CONTEXT_LOADING', 'INVESTIGATING', "
            "'ANALYZING', 'GENERATING_REPORT', 'COMPLETED', 'PARTIAL_RESULT', "
            "'FAILED', 'TIMEOUT', 'CANCELLED')",
            name="ck_task_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_task_progress"),
        CheckConstraint("fence >= 0", name="ck_task_fence"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    authorized_entity_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    permission_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    context_hash: Mapped[str | None] = mapped_column(String(64))
    lease_token: Mapped[str | None] = mapped_column(String(64))
    lease_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_task_id: Mapped[str | None] = mapped_column(ForeignKey("ai_analysis_task.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEventModel(Base):
    __tablename__ = "ai_task_event"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_task_event_sequence"),
        Index("ix_event_task_sequence", "task_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis_task.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_redacted: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxModel(Base):
    __tablename__ = "ai_outbox"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolExecutionModel(Base):
    __tablename__ = "ai_tool_execution"
    __table_args__ = (UniqueConstraint("task_id", "tool_id", "attempt"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis_task.id"), nullable=False)
    tool_id: Mapped[str] = mapped_column(String(64), nullable=False)
    args_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    result_ref: Mapped[str | None] = mapped_column(String(512))
    result_hash: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))


class EvidenceModel(Base):
    __tablename__ = "ai_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis_task.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    entity_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_ref: Mapped[str] = mapped_column(String(512), nullable=False)


class ModelAssessmentModel(Base):
    __tablename__ = "ai_model_assessment"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis_task.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question_version: Mapped[str] = mapped_column(String(32), nullable=False)
    primitive: Mapped[str] = mapped_column(String(16), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    requested_model: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_model: Mapped[str] = mapped_column(String(64), nullable=False)
    usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ReportModel(Base):
    __tablename__ = "ai_report"
    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_report_version"),
        CheckConstraint("version >= 1", name="ck_report_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis_task.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EngineerReviewModel(Base):
    __tablename__ = "ai_engineer_review"
    __table_args__ = (
        UniqueConstraint("task_id", "revision", name="uq_review_revision"),
        UniqueConstraint(
            "task_id", "idempotency_key", name="uq_review_idempotency_scope"
        ),
        CheckConstraint("report_version >= 1", name="ck_review_report_version"),
        CheckConstraint("revision >= 1", name="ck_review_revision"),
        CheckConstraint(
            "status IN ('CONFIRMED', 'CORRECTED', 'INCONCLUSIVE')",
            name="ck_review_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis_task.id"), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    helpful: Mapped[bool | None] = mapped_column(Boolean)
    confirmed_hypothesis_id: Mapped[str | None] = mapped_column(String(64))
    root_cause: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CaseBookArchiveModel(Base):
    __tablename__ = "ai_casebook_archive"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "idempotency_key", name="uq_archive_idempotency_scope"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ARCHIVED', 'FAILED')",
            name="ck_archive_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("ai_analysis_task.id"), nullable=False)
    review_id: Mapped[str] = mapped_column(ForeignKey("ai_engineer_review.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
