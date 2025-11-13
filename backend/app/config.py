from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Trainings Backoffice"
    environment: str = "local"
    database_url: str = "sqlite:///./trainings.db"
    openai_api_key: str | None = None


settings = Settings()
