from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PE_AGENT_", extra="ignore")

    app_name: str = "PE Case Analysis"
    environment: Literal["development", "test", "production"] = "development"
    platform_profile: Literal["mock", "platform"] = "mock"
    decision_profile: Literal["recorded", "typesafe"] = "recorded"
    explanation_profile: Literal["disabled", "openai_compatible"] = "disabled"
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
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 15.0
    llm_max_attempts: int = 2
    llm_max_backoff_seconds: float = 8.0
    llm_max_tokens: int = 1000

    @model_validator(mode="after")
    def reject_unconfigured_profiles(self) -> "Settings":
        if self.platform_profile == "platform" and not self.platform_base_url:
            raise ValueError("ADAPTER_NOT_CONFIGURED: platform base URL is required")
        if self.decision_profile == "typesafe" and not self.typesafe_base_url:
            raise ValueError("ADAPTER_NOT_CONFIGURED: TypeSafe base URL is required")
        if self.decision_profile == "typesafe" and not self.typesafe_api_key:
            raise ValueError("ADAPTER_NOT_CONFIGURED: TYPESAFE_API_KEY is required")
        if self.explanation_profile == "openai_compatible":
            if not self.llm_base_url:
                raise ValueError("ADAPTER_NOT_CONFIGURED: LLM base URL is required")
            if not self.llm_model:
                raise ValueError("ADAPTER_NOT_CONFIGURED: LLM model is required")
            if not self.llm_api_key:
                raise ValueError("ADAPTER_NOT_CONFIGURED: LLM_API_KEY is required")
            parsed_llm_url = urlparse(self.llm_base_url.strip())
            if (
                parsed_llm_url.scheme != "https"
                or not parsed_llm_url.hostname
                or parsed_llm_url.username
                or parsed_llm_url.password
            ):
                raise ValueError(
                    "ADAPTER_NOT_CONFIGURED: "
                    "LLM base URL must be HTTPS without credentials"
                )
            if parsed_llm_url.query or parsed_llm_url.fragment:
                raise ValueError(
                    "ADAPTER_NOT_CONFIGURED: "
                    "LLM base URL must not contain query or fragment"
                )
        required_values = (
            ("platform base URL", self.platform_base_url, self.platform_profile == "platform"),
            ("TypeSafe base URL", self.typesafe_base_url, self.decision_profile == "typesafe"),
            ("TYPESAFE_API_KEY", self.typesafe_api_key, self.decision_profile == "typesafe"),
            (
                "LLM base URL",
                self.llm_base_url,
                self.explanation_profile == "openai_compatible",
            ),
            ("LLM model", self.llm_model, self.explanation_profile == "openai_compatible"),
            ("LLM_API_KEY", self.llm_api_key, self.explanation_profile == "openai_compatible"),
        )
        for name, value, required in required_values:
            if required and value is not None and not value.strip():
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
            self.llm_timeout_seconds,
            self.llm_max_backoff_seconds,
        )
        if not all(isfinite(value) for value in numeric_settings):
            raise ValueError("worker, SSE, and LLM intervals must be finite")
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
        if self.llm_timeout_seconds <= 0.0 or self.llm_max_backoff_seconds < 0.0:
            raise ValueError("LLM timeout and backoff must be positive")
        if self.llm_max_attempts < 1 or self.llm_max_tokens < 1:
            raise ValueError("LLM attempts and max tokens must be positive")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
