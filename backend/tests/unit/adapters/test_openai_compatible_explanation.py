from __future__ import annotations

import asyncio

import httpx
import pytest

from pe_agent.adapters.explanations import (
    ExplanationAuthenticationError,
    ExplanationContractError,
    ExplanationRateLimitError,
    OpenAICompatibleExplanationAdapter,
)
from pe_agent.domain import ExplanationRequest


@pytest.mark.asyncio
async def test_openai_compatible_request_and_response_contract() -> None:
    api_key = "synthetic-llm-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.synthetic.invalid/v1/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {api_key}"
        payload = __import__("json").loads(request.content)
        assert payload["model"] == "synthetic-model"
        assert payload["temperature"] == 0
        assert payload["max_tokens"] == 256
        assert api_key not in request.content.decode()
        return httpx.Response(
            200,
            json={
                "model": "synthetic-model-2026-09",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Review the cited observations.",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleExplanationAdapter(
            base_url="https://llm.synthetic.invalid",
            api_key=api_key,
            model="synthetic-model",
            client=client,
            max_tokens=256,
        )
        result = await adapter.explain(
            ExplanationRequest(report_view={"summary": {"title": "Synthetic"}}, synthetic=True)
        )

    assert result.text == "Review the cited observations."
    assert result.requested_model == "synthetic-model"
    assert result.resolved_model == "synthetic-model-2026-09"
    assert (result.input_tokens, result.output_tokens) == (11, 7)


@pytest.mark.asyncio
async def test_authentication_error_does_not_leak_key_or_body() -> None:
    api_key = "never-expose-this"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"provider body {api_key}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleExplanationAdapter(
            base_url="https://llm.synthetic.invalid",
            api_key=api_key,
            model="synthetic-model",
            client=client,
        )
        with pytest.raises(ExplanationAuthenticationError) as raised:
            await adapter.explain(ExplanationRequest(report_view={}, synthetic=True))

    assert api_key not in str(raised.value)
    assert "provider body" not in str(raised.value)


@pytest.mark.asyncio
async def test_rate_limit_retries_are_bounded() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"Retry-After": "99"})

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleExplanationAdapter(
            base_url="https://llm.synthetic.invalid",
            api_key="synthetic-key",
            model="synthetic-model",
            client=client,
            max_attempts=2,
            max_backoff_seconds=3.0,
            sleeper=sleeper,
        )
        with pytest.raises(ExplanationRateLimitError):
            await adapter.explain(ExplanationRequest(report_view={}, synthetic=True))

    assert attempts == 2
    assert delays == [3.0]


@pytest.mark.asyncio
async def test_malformed_or_tool_only_response_is_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"tool_calls": [{"function": {"name": "x"}}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleExplanationAdapter(
            base_url="https://llm.synthetic.invalid",
            api_key="synthetic-key",
            model="synthetic-model",
            client=client,
        )
        with pytest.raises(ExplanationContractError):
            await adapter.explain(ExplanationRequest(report_view={}, synthetic=True))


@pytest.mark.asyncio
async def test_cancellation_is_not_retried() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise asyncio.CancelledError

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleExplanationAdapter(
            base_url="https://llm.synthetic.invalid",
            api_key="synthetic-key",
            model="synthetic-model",
            client=client,
        )
        with pytest.raises(asyncio.CancelledError):
            await adapter.explain(ExplanationRequest(report_view={}, synthetic=True))

    assert attempts == 1


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (" https://llm.synthetic.invalid ", "https://llm.synthetic.invalid/v1/chat/completions"),
        ("https://llm.synthetic.invalid/v1", "https://llm.synthetic.invalid/v1/chat/completions"),
        (
            "https://llm.synthetic.invalid/v1/chat/completions",
            "https://llm.synthetic.invalid/v1/chat/completions",
        ),
    ],
)
@pytest.mark.asyncio
async def test_common_openai_compatible_base_urls(base_url: str, expected: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == expected
        return httpx.Response(200, json={"choices": [{"message": {"content": "Safe text"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleExplanationAdapter(
            base_url=base_url,
            api_key="synthetic-key",
            model="synthetic-model",
            client=client,
        )
        await adapter.explain(ExplanationRequest(report_view={}, synthetic=True))


@pytest.mark.parametrize(
    "base_url",
    [
        "http://llm.synthetic.invalid",
        "https://user:pass@llm.synthetic.invalid",
        "https://llm.synthetic.invalid?key=value",
        "https://llm.synthetic.invalid#fragment",
    ],
)
def test_base_url_must_be_safe_https_origin(base_url: str) -> None:
    with pytest.raises(ValueError, match="LLM base URL"):
        OpenAICompatibleExplanationAdapter(
            base_url=base_url,
            api_key="synthetic-key",
            model="synthetic-model",
        )
