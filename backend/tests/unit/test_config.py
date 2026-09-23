from typing import Any

import pytest
from pydantic import ValidationError

from pe_agent.config import Settings


def test_default_profile_is_mock_recorded() -> None:
    settings = Settings()

    assert settings.platform_profile == "mock"
    assert settings.decision_profile == "recorded"
    assert settings.explanation_profile == "disabled"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"platform_profile": "platform"}, "platform base URL"),
        ({"platform_profile": "platform", "platform_base_url": "   "}, "blank"),
        ({"decision_profile": "typesafe"}, "TypeSafe base URL"),
        (
            {
                "decision_profile": "typesafe",
                "typesafe_base_url": "https://synthetic.invalid",
            },
            "TYPESAFE_API_KEY",
        ),
        (
            {
                "decision_profile": "typesafe",
                "typesafe_base_url": "https://synthetic.invalid",
                "typesafe_api_key": "   ",
            },
            "blank",
        ),
        ({"explanation_profile": "openai_compatible"}, "LLM base URL"),
        (
            {
                "explanation_profile": "openai_compatible",
                "llm_base_url": "https://llm.synthetic.invalid",
            },
            "LLM model",
        ),
        (
            {
                "explanation_profile": "openai_compatible",
                "llm_base_url": "https://llm.synthetic.invalid",
                "llm_model": "synthetic-model",
            },
            "LLM_API_KEY",
        ),
    ],
)
def test_external_profiles_fail_when_not_configured(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**overrides)


def test_disabled_optional_profiles_accept_compose_empty_strings() -> None:
    settings = Settings(
        platform_profile="mock",
        platform_base_url="",
        decision_profile="typesafe",
        typesafe_base_url="https://typesafe.synthetic.invalid",
        typesafe_api_key="synthetic-test-key",
        explanation_profile="disabled",
        llm_base_url="",
        llm_model="",
        llm_api_key="",
    )

    assert settings.platform_profile == "mock"
    assert settings.explanation_profile == "disabled"


def test_external_profiles_accept_explicit_configuration() -> None:
    settings = Settings(
        platform_profile="platform",
        platform_base_url="https://platform.synthetic.invalid",
        decision_profile="typesafe",
        typesafe_base_url="https://typesafe.synthetic.invalid",
        typesafe_api_key="synthetic-test-key",
        explanation_profile="openai_compatible",
        llm_base_url="https://llm.synthetic.invalid",
        llm_model="synthetic-model",
        llm_api_key="synthetic-llm-key",
    )

    assert settings.platform_profile == "platform"
    assert settings.decision_profile == "typesafe"
    assert settings.explanation_profile == "openai_compatible"


@pytest.mark.parametrize(
    "overrides",
    [
        {"environment": "production", "archive_enabled": True},
        {
            "platform_profile": "platform",
            "platform_base_url": "https://platform.synthetic.invalid",
            "archive_enabled": True,
        },
    ],
)
def test_mock_archive_rejects_non_mock_profiles(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="mock Case Book archive"):
        Settings(**overrides)


def test_mock_archive_accepts_explicit_nonproduction_mock_profile() -> None:
    settings = Settings(environment="test", platform_profile="mock", archive_enabled=True)

    assert settings.archive_enabled


def test_non_finite_intervals_are_rejected() -> None:
    with pytest.raises(ValidationError, match="finite"):
        Settings(sse_heartbeat_seconds=float("nan"))


def test_worker_timeout_must_fit_inside_lease() -> None:
    with pytest.raises(ValidationError, match="shorter than the lease"):
        Settings(worker_lease_seconds=10.0, worker_task_timeout_seconds=10.0)
