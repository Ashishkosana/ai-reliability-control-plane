from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://workflow:workflow@127.0.0.1:5432/aicp"
    api_host: str = "0.0.0.0"
    api_port: int = 43190
    openai_api_key: str = ""
    default_provider: str = "fake"
    log_level: str = "INFO"
    promote_threshold: float = 0.8
    max_body_bytes: int = 200_000
    demo_mode: bool = False


def load_settings() -> Settings:
    return Settings()
