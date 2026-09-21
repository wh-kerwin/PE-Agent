from __future__ import annotations

from typing import Protocol

from pe_agent.domain import CaseBookArchive, EngineerReview


class CaseBookPort(Protocol):
    async def archive(
        self,
        review: EngineerReview,
        idempotency_key: str,
    ) -> CaseBookArchive: ...
