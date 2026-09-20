from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PE_AGENT_", extra="ignore")

    app_name: str = "PE Case Analysis"
    environment: Literal["development", "test", "production"] = "development"
    platform_profile: Literal["mock", "platform"] = "mock"
    decision_profile: Literal["recorded", "typesafe"] = "recorded"


@lru_cache
def get_settings() -> Settings:
    return Settings()
