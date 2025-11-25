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
    cors_origins: list[str] = ["https://yellow-boat.org", "http://localhost:3000"]

    # Email settings
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "noreply@yellow-boat.org"
    smtp_from_name: str = "Yellow-Boat Academy"
    email_enabled: bool = False  # Set to True when SMTP is configured

    # IMAP settings for receiving emails
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True

    # Platform email domain
    platform_email_domain: str = "yellow-boat.org"
    frontend_base_url: str = "https://yellow-boat.org"


settings = Settings()
