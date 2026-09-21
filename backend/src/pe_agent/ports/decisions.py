from __future__ import annotations

from typing import Protocol

from pe_agent.domain import DecisionRequest, DecisionResult


class DecisionPort(Protocol):
    async def decide(self, request: DecisionRequest) -> DecisionResult: ...
