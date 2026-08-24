"""Settings and operational parameters for SRE AI."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class SREAISettings(BaseSettings):
    # Environment
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM Providers & API Keys
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    # Guardrail Limits
    max_specialist_iterations_incident: int = Field(default=15)
    max_specialist_iterations_default: int = Field(default=10)
    max_tool_result_chars: int = Field(default=50_000)
    max_cumulative_chars: int = Field(default=800_000)
    max_deep_dive_rounds: int = Field(default=2)
    llm_timeout_seconds: int = Field(default=90)
    llm_max_retries: int = Field(default=2)

    # Telemetry Endpoints (Optional external backends)
    prometheus_url: str = Field(default="http://localhost:9090", alias="PROMETHEUS_URL")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = SREAISettings()
