"""Application configuration for the Rule Service."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Rule Service settings loaded from environment variables."""

    app_name: str = "Daru Rule Service"
    app_version: str = "0.1.0"
    debug: bool = False

    api_prefix: str = "/api/v1"

    # OpenAI / LLM
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_base_url: str | None = None

    # Supabase
    supabase_url: str | None = None
    supabase_secret_key: str | None = None

    model_config = {
        "env_prefix": "DARU_",
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def clear_config_cache() -> None:
    """Clear cached configuration. Useful for testing."""
    get_settings.cache_clear()
