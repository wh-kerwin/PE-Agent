from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pe_agent.domain import AnalysisTask, EngineerReview, ReviewStatus, TaskStatus

NOW = datetime(2026, 9, 20, 1, 0, tzinfo=UTC)


def test_terminal_task_requires_completion_timestamp() -> None:
    with pytest.raises(ValidationError, match="terminal tasks require completedAt"):
        AnalysisTask(
            task_id="SYN-TASK",
            case_id="SYN-CASE",
            case_version="1",
            status=TaskStatus.COMPLETED,
            created_at=NOW,
            updated_at=NOW,
        )


def test_review_status_is_independent_from_completed_task() -> None:
    task = AnalysisTask(
        task_id="SYN-TASK",
        case_id="SYN-CASE",
        case_version="1",
        status=TaskStatus.COMPLETED,
        review_status=ReviewStatus.NOT_REVIEWED,
        created_at=NOW,
        updated_at=NOW,
        completed_at=NOW,
    )

    assert task.review_status is ReviewStatus.NOT_REVIEWED


def test_confirmed_review_requires_hypothesis() -> None:
    with pytest.raises(ValidationError, match="confirmedHypothesisId"):
        EngineerReview(
            task_id="SYN-TASK",
            report_version=1,
            revision=1,
            status=ReviewStatus.CONFIRMED,
            reviewed_at=NOW,
        )
