"""
Application configuration settings.

Loads configuration from environment variables using pydantic-settings.
Provides a single shared instance for application-wide access.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads and stores application configuration from environment variables."""

    # Application
    app_name: str = "Kavak Debate API"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str

    # Redis
    redis_url: str

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: int = 20

    # pydantic-settings configuration:
    # - Load variables from a .env file
    # - Ignore extra variables to avoid validation errors
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton settings instance for application-wide use
settings = Settings()
