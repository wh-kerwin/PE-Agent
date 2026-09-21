from __future__ import annotations

import asyncio
import json
import traceback

import httpx
import pytest

from pe_agent.adapters.decisions import (
    PINNED_TYPESAFE_MODEL,
    TypeSafeAuthenticationError,
    TypeSafeContractError,
    TypeSafeDecisionAdapter,
    TypeSafeRateLimitError,
    TypeSafeTimeoutError,
    build_typesafe_payload,
)
from pe_agent.domain import DecisionPrimitive, DecisionQuestion, DecisionRequest

ENDPOINT = "https://typesafe.synthetic.invalid/v1/systemone"
API_KEY = "super-secret-test-key"


def _request(primitive: DecisionPrimitive = DecisionPrimitive.NOUL) -> DecisionRequest:
    if primitive is DecisionPrimitive.CHOICE:
        criteria: dict[str, str] | tuple[str, ...] = {
            "SPC": "Inspect the synthetic SPC summary",
            "FDC": "Inspect the synthetic FDC summary",
        }
    elif primitive is DecisionPrimitive.SCORE:
        criteria = ("INSUFFICIENT", "WEAK", "MIXED", "STRONG")
    else:
        criteria = {"true": "Evidence is missing", "false": "Evidence is sufficient"}
    return DecisionRequest(
        state={
            "caseId": "SYN-CASE",
            "evidenceSummaries": [
                {
                    "evidenceId": "EV-SYN-1",
                    "summary": "Synthetic normalized evidence summary.",
                }
            ],
        },
        questions=(
            DecisionQuestion(
                question_id="assessment",
                primitive=primitive,
                instructions="Assess this synthetic state.",
                criteria=criteria,
            ),
        ),
        requested_model=PINNED_TYPESAFE_MODEL,
        question_set_version="synthetic-v1",
    )


def _success_payload(primitive: DecisionPrimitive) -> dict[str, object]:
    if primitive is DecisionPrimitive.CHOICE:
        answer: dict[str, object] = {
            "type": "choice",
            "choice": "SPC",
            "probabilities": {"SPC": 0.75, "FDC": 0.25},
            "confidence": 0.5,
        }
    elif primitive is DecisionPrimitive.SCORE:
        answer = {
            "type": "score",
            "score": 2.5,
            "legend": {"0": "INSUFFICIENT", "1": "WEAK", "2": "MIXED", "3": "STRONG"},
            "probabilities": {"0": 0.05, "1": 0.1, "2": 0.2, "3": 0.65},
            "confidence": 0.7,
        }
    else:
        answer = {"type": "noul", "noul": 0.8}
    return {
        "model": "jev-1.13.0",
        "answers": {"assessment": answer},
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


def _client(handler: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


@pytest.mark.asyncio
@pytest.mark.parametrize("primitive", list(DecisionPrimitive))
async def test_adapter_sends_exact_wire_shape_and_normalizes_responses(
    primitive: DecisionPrimitive,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_success_payload(primitive))

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(
            endpoint_url=ENDPOINT,
            api_key=API_KEY,
            client=client,
            clock=iter((10.0, 10.125)).__next__,
        )
        request = _request(primitive)
        result = await adapter.decide(request)

    assert captured[0].headers["Authorization"] == f"Bearer {API_KEY}"
    assert captured[0].url == ENDPOINT
    assert captured[0].method == "POST"
    assert captured[0].read()
    assert result.requested_model == request.requested_model
    assert result.resolved_model == "jev-1.13.0"
    assert result.question_set_version == "synthetic-v1"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 10
    assert result.usage.latency_ms == 125
    if primitive is DecisionPrimitive.NOUL:
        assert result.answers[0].answer == 0.8
        assert result.answers[0].distribution == {"false": pytest.approx(0.2), "true": 0.8}
        assert result.answers[0].confidence is None
    else:
        assert result.answers[0].confidence is not None

    assert json.loads(captured[0].content) == build_typesafe_payload(request)
    assert API_KEY.encode() not in captured[0].content
    assert b"questionSetVersion" not in captured[0].content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error_type"),
    [(401, TypeSafeAuthenticationError), (422, TypeSafeContractError)],
)
async def test_401_and_422_never_retry(status: int, error_type: type[Exception]) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"detail": f"contains {API_KEY}"})

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(
            endpoint_url=ENDPOINT,
            api_key=API_KEY,
            client=client,
            sleeper=sleeper,
        )
        with pytest.raises(error_type) as captured:
            await adapter.decide(_request())

    assert calls == 1
    assert sleeps == []
    assert API_KEY not in str(captured.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 529])
async def test_retryable_statuses_use_bounded_retry_after_without_sleeping(
    status: int,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(status, headers={"Retry-After": "60"})
        return httpx.Response(200, json=_success_payload(DecisionPrimitive.NOUL))

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(
            endpoint_url=ENDPOINT,
            api_key=API_KEY,
            client=client,
            sleeper=sleeper,
            max_backoff_seconds=2.0,
        )
        result = await adapter.decide(_request())

    assert result.answers[0].answer == 0.8
    assert calls == 3
    assert sleeps == [2.0, 2.0]


@pytest.mark.asyncio
async def test_429_stops_after_bounded_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    async def sleeper(delay: float) -> None:
        return None

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(
            endpoint_url=ENDPOINT,
            api_key=API_KEY,
            client=client,
            sleeper=sleeper,
            max_attempts=2,
        )
        with pytest.raises(TypeSafeRateLimitError):
            await adapter.decide(_request())

    assert calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        b'{"model":"jev-1.13.0","answers":{},"usage":{}}',
        b'{"model":"jev-1.13.0","answers":{"assessment":{"type":"noul","noul":2}},"usage":{"input_tokens":1,"output_tokens":1}}',
        b'{"model":"jev-1.13.0","answers":{"assessment":{"type":"noul","noul":NaN}},"usage":{"input_tokens":1,"output_tokens":1}}',
    ],
)
async def test_malformed_responses_are_rejected_without_body_leak(payload: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(endpoint_url=ENDPOINT, api_key=API_KEY, client=client)
        with pytest.raises(TypeSafeContractError, match="malformed TypeSafe response") as captured:
            await adapter.decide(_request())

    assert payload.decode(errors="ignore") not in str(captured.value)
    assert API_KEY not in str(captured.value)


@pytest.mark.asyncio
async def test_timeout_is_wrapped_and_secret_is_redacted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timed out with {API_KEY}", request=request)

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(endpoint_url=ENDPOINT, api_key=API_KEY, client=client)
        with pytest.raises(TypeSafeTimeoutError) as captured:
            await adapter.decide(_request())

    assert API_KEY not in str(captured.value)
    assert captured.value.__cause__ is None
    formatted = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert API_KEY not in formatted


@pytest.mark.asyncio
async def test_cancellation_propagates_and_is_not_retried() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(endpoint_url=ENDPOINT, api_key=API_KEY, client=client)
        with pytest.raises(asyncio.CancelledError):
            await adapter.decide(_request())

    assert calls == 1


def test_request_requires_pinned_model_and_rejects_raw_or_secret_state() -> None:
    with pytest.raises(ValueError, match="pinned"):
        build_typesafe_payload(
            _request().model_copy(update={"requested_model": "jev-latest"})
        )

    for forbidden_state in (
        {"rawPayload": "secret"},
        {"apiKey": "secret"},
        {"authorization": "secret"},
        {"token": "secret"},
        {"password": "secret"},
        {"accessToken": "secret"},
        {"client_secret": "secret"},
        {
            "evidenceSummaries": [
                {"evidenceId": "EV-SYN", "summary": "safe", "rawData": "secret"}
            ]
        },
    ):
        with pytest.raises(ValueError, match="normalized evidence summaries only"):
            build_typesafe_payload(
                _request().model_copy(update={"state": forbidden_state})
            )


def test_request_rejects_duplicate_question_ids_and_nonfinite_state() -> None:
    question = _request().questions[0]
    with pytest.raises(ValueError, match="unique"):
        build_typesafe_payload(
            _request().model_copy(update={"questions": (question, question)})
        )
    with pytest.raises(ValueError, match="non-finite"):
        build_typesafe_payload(
            _request().model_copy(update={"state": {"hypothesis": float("nan")}})
        )


@pytest.mark.asyncio
async def test_end_to_end_timeout_includes_retry_backoff() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1"})

    async with _client(httpx.MockTransport(handler)) as client:
        adapter = TypeSafeDecisionAdapter(
            endpoint_url=ENDPOINT,
            api_key=API_KEY,
            client=client,
            timeout_seconds=0.01,
            max_attempts=3,
        )
        with pytest.raises(TypeSafeTimeoutError):
            await adapter.decide(_request())
