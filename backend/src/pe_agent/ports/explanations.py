from typing import Protocol

from pe_agent.domain import ExplanationRequest, ExplanationResult


class ExplanationPort(Protocol):
    async def explain(self, request: ExplanationRequest) -> ExplanationResult: ...
