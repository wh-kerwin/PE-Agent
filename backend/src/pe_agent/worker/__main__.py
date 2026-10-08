from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress
from datetime import timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from pe_agent.adapters.decisions import RecordedDecisionAdapter, TypeSafeDecisionAdapter
from pe_agent.adapters.explanations import OpenAICompatibleExplanationAdapter
from pe_agent.adapters.mock_platform import MockPlatformAdapter
from pe_agent.adapters.persistence.session import create_engine, create_session_factory
from pe_agent.adapters.platform.template import AdapterNotConfiguredError
from pe_agent.application.yield_drop_workflow import YieldDropWorkflow
from pe_agent.config import Settings, get_settings
from pe_agent.ports import DecisionPort, ExplanationPort, PlatformDataPort
from pe_agent.testing import load_scenario
from pe_agent.worker.service import SqlWorkerCoordinator, WorkerRunner

LOGGER = logging.getLogger(__name__)


async def run_worker(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    stop_event = _install_signal_handlers()
    try:
        runner = _build_runner(settings, engine)
        while not stop_event.is_set():
            processed = await runner.run_once()
            if not processed:
                # Wait on the stop event with a timeout so a SIGTERM arriving
                # between polls is picked up within one poll interval.
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=settings.worker_poll_seconds,
                    )
        LOGGER.info("worker stop signal received; draining")
    finally:
        await engine.dispose()


def _install_signal_handlers() -> asyncio.Event:
    """Register SIGTERM/SIGINT handlers that set a shared stop event.

    Returns the event so tests can drive the stop path without relying on
    delivering an OS signal. Falls back to signal.signal on platforms where
    the asyncio loop cannot add a handler (Windows / non-main thread).
    """
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop(*_args: object) -> None:
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            with suppress(ValueError):
                signal.signal(sig, _request_stop)
    return stop_event


def _build_runner(settings: Settings, engine: AsyncEngine) -> WorkerRunner:
    platform = _build_platform(settings)
    decision = _build_decision(settings)
    return WorkerRunner(
        SqlWorkerCoordinator(create_session_factory(engine)),
        YieldDropWorkflow(platform),
        decision,
        explanation_port=_build_explanation(settings),
        lease_duration=timedelta(seconds=settings.worker_lease_seconds),
        task_timeout=timedelta(seconds=settings.worker_task_timeout_seconds),
    )


def _build_platform(settings: Settings) -> PlatformDataPort:
    if settings.platform_profile != "mock":
        raise AdapterNotConfiguredError("worker platform adapter")
    if settings.mock_scenario_path is None:
        raise AdapterNotConfiguredError("mock scenario path")
    return MockPlatformAdapter(load_scenario(settings.mock_scenario_path))


def _build_decision(settings: Settings) -> DecisionPort:
    if settings.decision_profile == "typesafe":
        if settings.typesafe_base_url is None or settings.typesafe_api_key is None:
            raise AdapterNotConfiguredError("TypeSafe decision adapter")
        return TypeSafeDecisionAdapter(
            endpoint_url=settings.typesafe_base_url,
            api_key=settings.typesafe_api_key,
        )
    recording = _recording_path(settings)
    return RecordedDecisionAdapter((recording,))


def _build_explanation(settings: Settings) -> ExplanationPort | None:
    if settings.explanation_profile == "disabled":
        return None
    if settings.llm_base_url is None or settings.llm_model is None or settings.llm_api_key is None:
        raise AdapterNotConfiguredError("OpenAI-compatible explanation adapter")
    return OpenAICompatibleExplanationAdapter(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_attempts=settings.llm_max_attempts,
        max_backoff_seconds=settings.llm_max_backoff_seconds,
        max_tokens=settings.llm_max_tokens,
    )


def _recording_path(settings: Settings) -> Path:
    if settings.mock_scenario_path is None:
        raise AdapterNotConfiguredError("mock scenario path")
    directory = settings.recorded_decision_dir
    if directory is None:
        directory = settings.mock_scenario_path.parent.parent / "decisions"
    path = directory / settings.mock_scenario_path.name
    if not path.is_file():
        raise AdapterNotConfiguredError(f"recorded decision {path.name}")
    return path


def main() -> None:
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker(get_settings()))


if __name__ == "__main__":
    main()
