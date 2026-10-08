from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pe_agent.adapters.decisions import RecordedDecisionAdapter, TypeSafeDecisionAdapter
from pe_agent.adapters.explanations import OpenAICompatibleExplanationAdapter
from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.adapters.platform.template import AdapterNotConfiguredError
from pe_agent.config import Settings
from pe_agent.worker import __main__ as worker_main
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


# ------------------------------------------------------------------
# SIGTERM graceful stop
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_signal_handlers_returns_event() -> None:
    """_install_signal_handlers returns an asyncio.Event (unset initially).

    This exercises the handler wiring without actually delivering an OS
    signal, so the test is deterministic across platforms.
    """
    stop_event = worker_main._install_signal_handlers()
    assert isinstance(stop_event, asyncio.Event)
    assert not stop_event.is_set()


@pytest.mark.asyncio
async def test_run_worker_stops_when_stop_event_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_worker exits its poll loop when the stop event is set.

    The runner and engine are stubbed; we drive the stop event directly
    instead of delivering a real SIGTERM, which is not reliable under a
    test runner.
    """
    poll_calls = 0
    stop_event = asyncio.Event()
    engine_disposed = False

    class StubEngine:
        async def dispose(self) -> None:
            nonlocal engine_disposed
            engine_disposed = True

    class StubRunner:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def run_once(self) -> bool:
            nonlocal poll_calls
            poll_calls += 1
            # Trigger the stop after the first poll so the loop exits.
            if poll_calls >= 1:
                stop_event.set()
            return False

    settings = _settings(worker_poll_seconds=0.01)

    # Replace the module-level factories with stubs that wire in our
    # stop_event so the real loop body drives the stop path.
    monkeypatch.setattr(worker_main, "create_engine", lambda url: StubEngine())
    monkeypatch.setattr(worker_main, "_build_runner", lambda s, e: StubRunner())
    monkeypatch.setattr(worker_main, "_install_signal_handlers", lambda: stop_event)

    await asyncio.wait_for(worker_main.run_worker(settings), timeout=2.0)

    assert poll_calls >= 1, "the poll loop ran at least once"
    assert engine_disposed, "the engine was disposed on the stop path"


def test_graceful_shutdown_window_is_positive_and_finite() -> None:
    settings = _settings(worker_graceful_shutdown_seconds=5.0)
    assert settings.worker_graceful_shutdown_seconds == 5.0

    with pytest.raises(ValueError, match="graceful shutdown"):
        _settings(worker_graceful_shutdown_seconds=0.0)

