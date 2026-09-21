from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pe_agent.adapters.decisions.questions import (
    DecisionResponseError,
    build_typesafe_payload,
    normalize_typesafe_answer,
    normalize_usage,
)
from pe_agent.domain import DecisionRequest, DecisionResult


class RecordedDecisionError(RuntimeError):
    """A recording is missing, malformed, or does not match the request."""


class RecordedDecisionAdapter:
    """Deterministic decision port backed by explicitly synthetic recordings."""

    def __init__(self, recordings: Sequence[Path | Mapping[str, Any]]) -> None:
        if not recordings:
            raise RecordedDecisionError("at least one synthetic recording is required")
        self._recordings = tuple(_load_recording(recording) for recording in recordings)

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        expected_request = build_typesafe_payload(request)
        matches = [
            recording
            for recording in self._recordings
            if _matches(
                recording["request"],
                expected_request,
                request.question_set_version,
            )
        ]
        if len(matches) != 1:
            raise RecordedDecisionError(
                "expected exactly one synthetic recording for the decision request"
            )

        response = _as_mapping(matches[0]["response"], "recorded response")
        answers_payload = _as_mapping(response.get("answers"), "recorded answers")
        expected_ids = {question.question_id for question in request.questions}
        if set(answers_payload) != expected_ids:
            raise RecordedDecisionError(
                "recorded response must answer every requested question exactly once"
            )
        resolved_model = response.get("model")
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            raise RecordedDecisionError("recorded response model must be a non-empty string")

        try:
            return DecisionResult(
                requested_model=request.requested_model,
                resolved_model=resolved_model,
                question_set_version=request.question_set_version,
                answers=tuple(
                    normalize_typesafe_answer(question, answers_payload[question.question_id])
                    for question in request.questions
                ),
                usage=normalize_usage(response.get("usage")),
            )
        except DecisionResponseError as exc:
            raise RecordedDecisionError(f"malformed recorded response: {exc}") from exc


def _load_recording(recording: Path | Mapping[str, Any]) -> Mapping[str, object]:
    if isinstance(recording, Path):
        try:
            payload: object = json.loads(recording.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecordedDecisionError(f"could not load recording {recording.name}") from exc
    else:
        payload = recording
    parsed = _as_mapping(payload, "recording")
    if parsed.get("synthetic") is not True:
        raise RecordedDecisionError("recordings must be explicitly marked synthetic")
    request_payload = _as_mapping(parsed.get("request"), "recorded request")
    version = request_payload.get("questionSetVersion")
    if not isinstance(version, str) or not version.strip():
        raise RecordedDecisionError("recorded request requires questionSetVersion metadata")
    _as_mapping(parsed.get("response"), "recorded response")
    return parsed


def _matches(
    recorded: object,
    expected: Mapping[str, object],
    question_set_version: str,
) -> bool:
    payload = _as_mapping(recorded, "recorded request")
    if payload.get("questionSetVersion") != question_set_version:
        return False
    wire_payload = {key: value for key, value in payload.items() if key != "questionSetVersion"}
    return wire_payload == expected


def _as_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise RecordedDecisionError(f"{name} must be an object")
    return value
