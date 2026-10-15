"""pydantic-settings. Reads backend/.env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # pydantic-settings: reads backend/.env and validates types, so a missing
    # key fails at startup instead of deep inside a request.
    # Run commands from the backend/ folder so ".env" is found.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str
    PRIMARY_MODEL: str = "gemini/gemini-3.6-flash"
    FALLBACK_MODEL: str = "ollama/qwen2.5vl"
    REFINE_ROUNDS: int = 2
    MAX_RETRIES: int = 2  # retries per model before moving to the fallback


settings = Settings()