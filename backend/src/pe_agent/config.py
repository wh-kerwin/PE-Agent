from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PE_AGENT_", extra="ignore")

    app_name: str = "PE Case Analysis"
    environment: Literal["development", "test", "production"] = "development"
    platform_profile: Literal["mock", "platform"] = "mock"
    decision_profile: Literal["recorded", "typesafe"] = "recorded"
    database_url: str = "postgresql+asyncpg://pe_agent:pe_agent@localhost:5432/pe_agent"
    archive_enabled: bool = False
    mock_scenario_path: Path | None = None
    recorded_decision_dir: Path | None = None
    worker_poll_seconds: float = 2.0
    worker_lease_seconds: float = 60.0
    worker_task_timeout_seconds: float = 45.0
    sse_poll_seconds: float = 0.5
    sse_heartbeat_seconds: float = 15.0
    sse_permission_recheck_seconds: float = 15.0
    sse_replay_limit: int = 500
    platform_base_url: str | None = None
    typesafe_base_url: str | None = None
    typesafe_api_key: str | None = None

    @model_validator(mode="after")
    def reject_unconfigured_profiles(self) -> "Settings":
        if self.platform_profile == "platform" and not self.platform_base_url:
            raise ValueError("ADAPTER_NOT_CONFIGURED: platform base URL is required")
        if self.decision_profile == "typesafe" and not self.typesafe_base_url:
            raise ValueError("ADAPTER_NOT_CONFIGURED: TypeSafe base URL is required")
        if self.decision_profile == "typesafe" and not self.typesafe_api_key:
            raise ValueError("ADAPTER_NOT_CONFIGURED: TYPESAFE_API_KEY is required")
        for name, value in (
            ("platform base URL", self.platform_base_url),
            ("TypeSafe base URL", self.typesafe_base_url),
            ("TYPESAFE_API_KEY", self.typesafe_api_key),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"ADAPTER_NOT_CONFIGURED: {name} is blank")
        if self.archive_enabled and (
            self.environment == "production" or self.platform_profile != "mock"
        ):
            raise ValueError(
                "ADAPTER_NOT_CONFIGURED: mock Case Book archive requires the mock platform profile"
            )
        numeric_settings = (
            self.worker_poll_seconds,
            self.worker_lease_seconds,
            self.worker_task_timeout_seconds,
            self.sse_poll_seconds,
            self.sse_heartbeat_seconds,
            self.sse_permission_recheck_seconds,
        )
        if not all(isfinite(value) for value in numeric_settings):
            raise ValueError("worker and SSE intervals must be finite")
        if self.worker_poll_seconds <= 0.0:
            raise ValueError("worker poll interval must be positive")
        if self.worker_lease_seconds <= 0.0 or self.worker_task_timeout_seconds <= 0.0:
            raise ValueError("worker lease and timeout must be positive")
        if self.worker_task_timeout_seconds >= self.worker_lease_seconds:
            raise ValueError("worker task timeout must be shorter than the lease")
        if (
            self.sse_poll_seconds <= 0.0
            or self.sse_heartbeat_seconds <= 0.0
            or self.sse_permission_recheck_seconds <= 0.0
            or self.sse_replay_limit <= 0
        ):
            raise ValueError("SSE intervals and replay limit must be positive")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
