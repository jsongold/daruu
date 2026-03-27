"""Application configuration."""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Daru PDF Simple"
    app_version: str = "0.1.0"
    debug: bool = False

    api_prefix: str = "/api"
    allowed_origins: str = "*"

    upload_dir: Path = Path("/tmp/daru-pdf-uploads")
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Supabase (required)
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
    return Settings()
