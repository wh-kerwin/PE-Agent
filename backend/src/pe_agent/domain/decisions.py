from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from pe_agent.domain.base import DomainModel, NonEmptyStr
from pe_agent.domain.enums import DecisionPrimitive


class DecisionQuestion(DomainModel):
    question_id: NonEmptyStr
    primitive: DecisionPrimitive
    instructions: NonEmptyStr
    criteria: dict[NonEmptyStr, NonEmptyStr] | tuple[NonEmptyStr, ...]


class DecisionRequest(DomainModel):
    state: dict[str, Any]
    questions: tuple[DecisionQuestion, ...] = Field(min_length=1)
    requested_model: NonEmptyStr
    question_set_version: NonEmptyStr


class DecisionAnswer(DomainModel):
    question_id: NonEmptyStr
    primitive: DecisionPrimitive
    answer: NonEmptyStr | float
    distribution: dict[NonEmptyStr, float]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_primitive_result(self) -> DecisionAnswer:
        total = sum(self.distribution.values())
        if self.distribution and abs(total - 1.0) > 1e-6:
            raise ValueError("decision distribution must sum to 1")
        if any(
            probability < 0.0 or probability > 1.0
            for probability in self.distribution.values()
        ):
            raise ValueError("decision probabilities must be between 0 and 1")
        if self.primitive is DecisionPrimitive.NOUL and self.confidence is not None:
            raise ValueError("Noul answers do not carry confidence")
        if self.primitive is not DecisionPrimitive.NOUL and self.confidence is None:
            raise ValueError("choice and score answers require confidence")
        return self


class DecisionUsage(DomainModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int | None = Field(default=None, ge=0)


class DecisionResult(DomainModel):
    requested_model: NonEmptyStr
    resolved_model: NonEmptyStr
    question_set_version: NonEmptyStr
    answers: tuple[DecisionAnswer, ...]
    usage: DecisionUsage
