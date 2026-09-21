from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pe_agent.domain.decisions import DecisionResult
from pe_agent.domain.enums import TaskStatus
from pe_agent.domain.platform import CaseContext
from pe_agent.domain.tools import ToolResult


@dataclass(frozen=True)
class ReportInput:
    task_id: str
    report_version: int
    context: CaseContext
    results: tuple[ToolResult[Any], ...]
    skipped_sources: tuple[str, ...]
    authorized_entity_ids: frozenset[str]
    generated_at: datetime
    requested_model: str
    resolved_model: str
    question_set_version: str
    decision: DecisionResult | None = None


@dataclass(frozen=True)
class ReportOutcome:
    report: dict[str, Any] | None
    terminal_status: TaskStatus
    validation_errors: tuple[str, ...] = ()
