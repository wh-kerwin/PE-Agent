from __future__ import annotations

from pathlib import Path

import pytest

from pe_agent.adapters.decisions import RecordedDecisionAdapter, TypeSafeDecisionAdapter
from pe_agent.adapters.explanations import OpenAICompatibleExplanationAdapter
from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.adapters.platform.template import AdapterNotConfiguredError
from pe_agent.config import Settings
from pe_agent.worker.__main__ import _build_decision, _build_explanation, _build_platform

FIXTURES = Path(__file__).parents[2] / "fixtures"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "mock_scenario_path": FIXTURES / "scenarios" / "pressure-drift-success.json",
        "recorded_decision_dir": FIXTURES / "decisions",
    }
    values.update(overrides)
    return Settings(**values)


def test_mock_recorded_worker_adapters_are_explicitly_configured() -> None:
    settings = _settings()

    assert isinstance(_build_platform(settings), MockPlatformAdapter)
    assert isinstance(_build_decision(settings), RecordedDecisionAdapter)
    assert _build_explanation(settings) is None


def test_customer_platform_worker_fails_closed() -> None:
    settings = _settings(
        platform_profile="platform",
        platform_base_url="https://platform.synthetic.invalid",
    )

    with pytest.raises(AdapterNotConfiguredError, match="worker platform adapter"):
        _build_platform(settings)


def test_missing_recording_fails_closed(tmp_path: Path) -> None:
    settings = _settings(recorded_decision_dir=tmp_path)

    with pytest.raises(AdapterNotConfiguredError, match="recorded decision"):
        _build_decision(settings)


def test_typesafe_worker_requires_and_uses_explicit_configuration() -> None:
    settings = _settings(
        decision_profile="typesafe",
        typesafe_base_url="https://typesafe.synthetic.invalid",
        typesafe_api_key="synthetic-test-key",
    )

    assert isinstance(_build_decision(settings), TypeSafeDecisionAdapter)


def test_openai_compatible_explanation_uses_separate_configuration() -> None:
    settings = _settings(
        explanation_profile="openai_compatible",
        llm_base_url="https://llm.synthetic.invalid",
        llm_model="synthetic-model",
        llm_api_key="synthetic-llm-key",
    )

    assert isinstance(_build_explanation(settings), OpenAICompatibleExplanationAdapter)
    assert isinstance(_build_decision(settings), RecordedDecisionAdapter)
