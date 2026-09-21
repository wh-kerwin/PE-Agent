from __future__ import annotations

from typing import Protocol, TypeVar

from pe_agent.domain import AnalysisTask, EngineerReview, Evidence

T = TypeVar("T")


class Repository(Protocol[T]):
    async def get(self, item_id: str) -> T | None: ...

    async def save(self, item: T) -> None: ...


class TaskRepository(Repository[AnalysisTask], Protocol):
    async def find_running(self, case_id: str, case_version: str) -> AnalysisTask | None: ...


class EvidenceRepository(Protocol):
    async def add(self, task_id: str, evidence: Evidence) -> None: ...

    async def list_for_task(self, task_id: str) -> tuple[Evidence, ...]: ...


class ReviewRepository(Protocol):
    async def save(self, review: EngineerReview) -> None: ...

    async def latest_for_task(self, task_id: str) -> EngineerReview | None: ...
