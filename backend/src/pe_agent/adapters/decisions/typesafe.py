from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

import httpx

from pe_agent.adapters.decisions.questions import (
    DecisionResponseError,
    build_typesafe_payload,
    normalize_typesafe_answer,
    normalize_usage,
)
from pe_agent.domain import DecisionRequest, DecisionResult

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]
Jitter = Callable[[], float]


class TypeSafeError(RuntimeError):
    """Base error safe to expose without credentials or response bodies."""


class TypeSafeAuthenticationError(TypeSafeError):
    """TypeSafe rejected the configured API key."""


class TypeSafeContractError(TypeSafeError):
    """The request or response violated the TypeSafe decision contract."""


class TypeSafeRateLimitError(TypeSafeError):
    """TypeSafe rate limiting remained after bounded retries."""


class TypeSafeUnavailableError(TypeSafeError):
    """TypeSafe could not serve the request."""


class TypeSafeTimeoutError(TypeSafeError):
    """The TypeSafe request exceeded its configured timeout."""


class TypeSafeDecisionAdapter:
    """Raw HTTP adapter for the TypeSafe System One decision endpoint."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
        max_attempts: int = 3,
        max_backoff_seconds: float = 8.0,
        sleeper: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
        jitter: Jitter = random.random,
    ) -> None:
        if not endpoint_url.strip():
            raise ValueError("TypeSafe endpoint URL is required")
        if not api_key.strip():
            raise ValueError("TypeSafe API key is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if timeout_seconds <= 0.0 or max_backoff_seconds < 0.0:
            raise ValueError("timeout and backoff must be positive")
        self._endpoint_url = endpoint_url
        self._api_key = api_key
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._max_backoff_seconds = max_backoff_seconds
        self._sleeper = sleeper
        self._clock = clock
        self._jitter = jitter

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        try:
            payload = build_typesafe_payload(request)
        except ValueError:
            raise TypeSafeContractError("invalid TypeSafe decision request") from None

        started_at = self._clock()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._post_with_retries(payload)
        except TimeoutError:
            raise TypeSafeTimeoutError("TypeSafe request timed out") from None
        latency_ms = max(0, round((self._clock() - started_at) * 1000))
        try:
            body: object = response.json()
            response_payload = _require_mapping(body, "response")
            resolved_model = _require_nonempty_string(response_payload.get("model"), "model")
            answers_payload = _require_mapping(response_payload.get("answers"), "answers")
            expected_ids = {question.question_id for question in request.questions}
            if set(answers_payload) != expected_ids:
                raise DecisionResponseError(
                    "response must answer every requested question exactly once"
                )
            return DecisionResult(
                requested_model=request.requested_model,
                resolved_model=resolved_model,
                question_set_version=request.question_set_version,
                answers=tuple(
                    normalize_typesafe_answer(question, answers_payload[question.question_id])
                    for question in request.questions
                ),
                usage=normalize_usage(response_payload.get("usage"), latency_ms=latency_ms),
            )
        except (ValueError, TypeError, DecisionResponseError):
            raise TypeSafeContractError("malformed TypeSafe response") from None

    async def _post_with_retries(self, payload: Mapping[str, object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(self._max_attempts):
            try:
                response = await self._post(payload, headers)
            except httpx.TimeoutException:
                raise TypeSafeTimeoutError("TypeSafe request timed out") from None
            except httpx.RequestError:
                raise TypeSafeUnavailableError("TypeSafe request failed") from None

            if response.status_code == 401:
                raise TypeSafeAuthenticationError("TypeSafe authentication failed")
            if response.status_code == 422:
                raise TypeSafeContractError("TypeSafe rejected the request contract")
            if response.status_code in (429, 529):
                if attempt + 1 == self._max_attempts:
                    error_type = (
                        TypeSafeRateLimitError
                        if response.status_code == 429
                        else TypeSafeUnavailableError
                    )
                    raise error_type(
                        f"TypeSafe returned HTTP {response.status_code} after bounded retries"
                    )
                await self._sleeper(self._retry_delay(response, attempt))
                continue
            if response.is_error:
                raise TypeSafeUnavailableError(
                    f"TypeSafe returned unexpected HTTP {response.status_code}"
                )
            return response
        raise AssertionError("retry loop exited unexpectedly")

    async def _post(
        self,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                self._endpoint_url,
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        async with httpx.AsyncClient() as client:
            return await client.post(
                self._endpoint_url,
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                parsed = float(retry_after)
            except ValueError:
                parsed = -1.0
            if parsed >= 0.0:
                return min(parsed, self._max_backoff_seconds)
        exponential = 0.5 * (2**attempt)
        jittered = exponential * (0.75 + 0.5 * self._jitter())
        return cast(float, min(jittered, self._max_backoff_seconds))


def _require_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DecisionResponseError(f"{name} must be an object")
    return value


def _require_nonempty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionResponseError(f"{name} must be a non-empty string")
    return value
