from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExplanationRequest:
    report_view: dict[str, Any]
    synthetic: bool


@dataclass(frozen=True)
class ExplanationResult:
    text: str
    requested_model: str
    resolved_model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
