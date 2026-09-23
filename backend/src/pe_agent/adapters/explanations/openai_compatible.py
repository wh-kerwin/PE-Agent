from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from pe_agent.domain import ExplanationRequest, ExplanationResult

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]
Jitter = Callable[[], float]


class ExplanationError(RuntimeError):
    """Base error safe to expose without credentials or provider payloads."""


class ExplanationAuthenticationError(ExplanationError):
    pass


class ExplanationContractError(ExplanationError):
    pass


class ExplanationRateLimitError(ExplanationError):
    pass


class ExplanationUnavailableError(ExplanationError):
    pass


class ExplanationTimeoutError(ExplanationError):
    pass


class OpenAICompatibleExplanationAdapter:
    """Minimal, non-streaming OpenAI-compatible chat-completions adapter."""

    _MAX_RESPONSE_BYTES = 1_000_000

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
        max_attempts: int = 2,
        max_backoff_seconds: float = 8.0,
        max_tokens: int = 1000,
        sleeper: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
        jitter: Jitter = random.random,
    ) -> None:
        parsed = urlparse(base_url.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("LLM base URL must be an HTTPS origin without credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("LLM base URL must not contain query or fragment data")
        if not api_key.strip():
            raise ValueError("LLM API key is required")
        if not model.strip():
            raise ValueError("LLM model is required")
        if timeout_seconds <= 0.0 or max_backoff_seconds < 0.0:
            raise ValueError("timeout and backoff must be positive")
        if max_attempts < 1 or max_tokens < 1:
            raise ValueError("attempts and max tokens must be positive")
        normalized_url = base_url.strip().rstrip("/")
        if normalized_url.endswith("/chat/completions"):
            self._endpoint_url = normalized_url
        elif normalized_url.endswith("/v1"):
            self._endpoint_url = normalized_url + "/chat/completions"
        else:
            self._endpoint_url = normalized_url + "/v1/chat/completions"
        self._api_key = api_key
        self._model = model
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._max_backoff_seconds = max_backoff_seconds
        self._max_tokens = max_tokens
        self._sleeper = sleeper
        self._clock = clock
        self._jitter = jitter

    async def explain(self, request: ExplanationRequest) -> ExplanationResult:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rewrite only the supplied report view as concise engineer-facing prose. "
                        "Do not add facts, causation, evidence IDs, permissions, or conclusions."
                    ),
                },
                {"role": "user", "content": _render_report_view(request.report_view)},
            ],
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        started_at = self._clock()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._post_with_retries(payload)
        except ExplanationError:
            raise
        except TimeoutError:
            raise ExplanationTimeoutError("LLM request timed out") from None
        latency_ms = max(0, round((self._clock() - started_at) * 1000))
        if len(response.content) > self._MAX_RESPONSE_BYTES:
            raise ExplanationContractError("LLM response is too large")
        try:
            body = _require_mapping(response.json())
            choices = body.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("choices")
            choice = _require_mapping(choices[0])
            message = _require_mapping(choice.get("message"))
            text = message.get("content")
            if not isinstance(text, str) or not text.strip() or len(text) > 12000:
                raise ValueError("content")
            usage = body.get("usage")
            input_tokens, output_tokens = _usage(usage)
            resolved_model = body.get("model", self._model)
            if not isinstance(resolved_model, str) or not resolved_model.strip():
                raise ValueError("model")
            return ExplanationResult(
                text=text.strip(),
                requested_model=self._model,
                resolved_model=resolved_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        except (ValueError, TypeError):
            raise ExplanationContractError("malformed LLM response") from None

    async def _post_with_retries(self, payload: Mapping[str, object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        for attempt in range(self._max_attempts):
            try:
                response = await self._post(payload, headers)
            except httpx.TimeoutException:
                raise ExplanationTimeoutError("LLM request timed out") from None
            except httpx.RequestError:
                raise ExplanationUnavailableError("LLM request failed") from None
            if response.status_code in (401, 403):
                raise ExplanationAuthenticationError("LLM authentication failed")
            if response.status_code in (400, 404, 422):
                raise ExplanationContractError("LLM rejected the request contract")
            if response.status_code in (408, 429, 500, 502, 503, 529):
                if attempt + 1 == self._max_attempts:
                    if response.status_code in (408, 429):
                        raise ExplanationRateLimitError(
                            f"LLM returned HTTP {response.status_code} after bounded retries"
                        )
                    raise ExplanationUnavailableError(
                        f"LLM returned HTTP {response.status_code} after bounded retries"
                    )
                await self._sleeper(self._retry_delay(response, attempt))
                continue
            if response.is_error:
                raise ExplanationUnavailableError(
                    f"LLM returned unexpected HTTP {response.status_code}"
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
        return cast(
            float,
            min(
                exponential * (0.75 + 0.5 * self._jitter()),
                self._max_backoff_seconds,
            ),
        )


def _render_report_view(view: dict[str, Any]) -> str:
    import json

    return json.dumps(view, ensure_ascii=False, separators=(",", ":"))


def _require_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError("object")
    return value


def _usage(value: object) -> tuple[int, int]:
    if value is None:
        return 0, 0
    usage = _require_mapping(value)
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    if (
        not isinstance(prompt, int)
        or prompt < 0
        or not isinstance(completion, int)
        or completion < 0
    ):
        raise ValueError("usage")
    return prompt, completion
