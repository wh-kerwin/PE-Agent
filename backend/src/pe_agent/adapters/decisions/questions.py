from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

from pe_agent.domain import (
    DecisionAnswer,
    DecisionPrimitive,
    DecisionQuestion,
    DecisionRequest,
    DecisionUsage,
)

PINNED_TYPESAFE_MODEL = "jev-1.13.0"

_ALLOWED_TOP_LEVEL_STATE_KEYS = frozenset(
    {
        "caseId",
        "evidenceIds",
        "evidenceSummaries",
        "hypothesis",
        "synthetic",
    }
)
_ALLOWED_EVIDENCE_SUMMARY_KEYS = frozenset(
    {
        "evidenceId",
        "kind",
        "observation",
        "quality",
        "summary",
        "warnings",
    }
)


class DecisionRequestError(ValueError):
    """A decision request cannot be represented by the TypeSafe contract."""


class DecisionResponseError(ValueError):
    """A TypeSafe response does not satisfy the decision contract."""


def normalize_typesafe_answer(
    question: DecisionQuestion,
    payload: object,
) -> DecisionAnswer:
    """Normalize one Choice, Score, or Noul response into the domain model."""
    answer_payload = _require_mapping(payload, f"answer {question.question_id!r}")
    response_type = answer_payload.get("type")
    if response_type != question.primitive.value:
        raise DecisionResponseError(
            f"answer {question.question_id!r} has unexpected primitive {response_type!r}"
        )

    if question.primitive is DecisionPrimitive.NOUL:
        noul = _require_probability(answer_payload.get("noul"), "noul")
        return DecisionAnswer(
            question_id=question.question_id,
            primitive=question.primitive,
            answer=noul,
            distribution={"false": 1.0 - noul, "true": noul},
            confidence=None,
        )

    probabilities = _normalize_distribution(answer_payload.get("probabilities"))
    confidence = _require_probability(answer_payload.get("confidence"), "confidence")
    if question.primitive is DecisionPrimitive.CHOICE:
        choice = answer_payload.get("choice")
        if not isinstance(choice, str) or not choice.strip():
            raise DecisionResponseError("choice must be a non-empty string")
        if not isinstance(question.criteria, dict) or set(probabilities) != set(question.criteria):
            raise DecisionResponseError("choice probabilities must match requested criteria")
        if choice not in question.criteria:
            raise DecisionResponseError("choice is not one of the requested criteria")
        answer: str | float = choice
    else:
        score = answer_payload.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise DecisionResponseError("score must be numeric")
        score_value = float(score)
        if not isinstance(question.criteria, tuple):
            raise DecisionResponseError("score request criteria are not ordered")
        expected_keys = {str(index) for index in range(len(question.criteria))}
        if set(probabilities) != expected_keys:
            raise DecisionResponseError("score probabilities must match requested criteria")
        if (
            not isfinite(score_value)
            or score_value < 0.0
            or score_value > len(question.criteria) - 1
        ):
            raise DecisionResponseError("score is outside the requested rubric")
        legend = _require_mapping(answer_payload.get("legend"), "legend")
        expected_legend = {
            str(index): criterion.split(":", 1)[0].strip()
            for index, criterion in enumerate(question.criteria)
        }
        if legend != expected_legend:
            raise DecisionResponseError("score legend does not match requested criteria")
        answer = score_value

    return DecisionAnswer(
        question_id=question.question_id,
        primitive=question.primitive,
        answer=answer,
        distribution=probabilities,
        confidence=confidence,
    )


def normalize_usage(payload: object, *, latency_ms: int | None = None) -> DecisionUsage:
    usage = _require_mapping(payload, "usage")
    input_tokens = _require_nonnegative_int(usage.get("input_tokens"), "input_tokens")
    output_tokens = _require_nonnegative_int(usage.get("output_tokens"), "output_tokens")
    return DecisionUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )


def build_typesafe_payload(request: DecisionRequest) -> dict[str, object]:
    """Build the exact System One wire payload from a validated domain request."""
    if request.requested_model != PINNED_TYPESAFE_MODEL:
        raise DecisionRequestError(
            f"requested model must be pinned to {PINNED_TYPESAFE_MODEL}"
        )

    question_ids = [question.question_id for question in request.questions]
    if len(question_ids) != len(set(question_ids)):
        raise DecisionRequestError("question IDs must be unique")

    return {
        "state": _normalize_state(request.state),
        "model": PINNED_TYPESAFE_MODEL,
        "questions": {
            question.question_id: _serialize_question(question)
            for question in request.questions
        },
    }


def _serialize_question(question: DecisionQuestion) -> dict[str, object]:
    criteria: object
    if question.primitive in (DecisionPrimitive.CHOICE, DecisionPrimitive.NOUL):
        if not isinstance(question.criteria, dict):
            raise DecisionRequestError(
                f"{question.primitive.value} question {question.question_id!r} "
                "requires keyed criteria"
            )
        if question.primitive is DecisionPrimitive.NOUL and set(question.criteria) != {
            "true",
            "false",
        }:
            raise DecisionRequestError(
                f"noul question {question.question_id!r} requires true and false criteria"
            )
        criteria = dict(question.criteria)
    else:
        if not isinstance(question.criteria, tuple):
            raise DecisionRequestError(
                f"score question {question.question_id!r} requires ordered criteria"
            )
        criteria = list(question.criteria)

    return {
        "type": question.primitive.value,
        "instructions": question.instructions,
        "criteria": criteria,
    }


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DecisionResponseError(f"{name} must be an object")
    return value


def _require_probability(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionResponseError(f"{name} must be numeric")
    probability = float(value)
    if not isfinite(probability) or probability < 0.0 or probability > 1.0:
        raise DecisionResponseError(f"{name} must be between 0 and 1")
    return probability


def _require_nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DecisionResponseError(f"{name} must be a non-negative integer")
    return value


def _normalize_distribution(value: object) -> dict[str, float]:
    payload = _require_mapping(value, "probabilities")
    distribution = {
        key: _require_probability(probability, f"probabilities.{key}")
        for key, probability in payload.items()
    }
    if not distribution or abs(sum(distribution.values()) - 1.0) > 1e-6:
        raise DecisionResponseError("probabilities must sum to 1")
    return distribution


def _normalize_state(state: Mapping[str, Any]) -> dict[str, object]:
    unknown_keys = set(state) - _ALLOWED_TOP_LEVEL_STATE_KEYS
    if unknown_keys:
        raise DecisionRequestError(
            "state contains unsupported fields; send normalized evidence summaries only"
        )
    normalized = {
        key: _normalize_json(value, path=f"state.{key}")
        for key, value in state.items()
    }
    summaries = state.get("evidenceSummaries", [])
    if not isinstance(summaries, Sequence) or isinstance(summaries, (str, bytes, bytearray)):
        raise DecisionRequestError("state.evidenceSummaries must be an array")
    for index, summary in enumerate(summaries):
        if not isinstance(summary, Mapping) or not all(isinstance(key, str) for key in summary):
            raise DecisionRequestError(
                f"state.evidenceSummaries[{index}] must be an object"
            )
        if set(summary) - _ALLOWED_EVIDENCE_SUMMARY_KEYS:
            raise DecisionRequestError(
                "state evidence contains unsupported fields; send normalized evidence "
                "summaries only"
            )
    return normalized


def _normalize_json(value: Any, *, path: str) -> object:
    """Copy allowlisted JSON state while rejecting raw records and non-finite values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise DecisionRequestError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DecisionRequestError(f"{path} contains a non-string key")
            normalized[key] = _normalize_json(item, path=f"{path}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise DecisionRequestError(f"{path} contains a non-JSON value")
