from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Load and store application configuration from environment variables."""

    app_name: str = "Kavak Debate API"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str

    # Redis
    redis_url: str

    # OpenAI API
    openai_api_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single instance to be imported across the application
settings = Settings()
