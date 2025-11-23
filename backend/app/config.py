from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the backend directory (parent of app directory)
BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Yellow-Boat Academy"
    environment: str = "local"
    database_url: str = "sqlite:///./trainings.db"
    openai_api_key: str | None = None

    # Authentication settings
    secret_key: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS settings
    cors_origins: list[str] = ["https://bo.yellow-plane.com", "http://localhost:3000"]


settings = Settings()
