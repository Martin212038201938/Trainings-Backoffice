"""Test for configuration and settings."""

from app.config import settings


def test_settings_exist():
    """Test that settings are loaded."""
    assert settings.app_name
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes > 0


def test_cors_origins_configured():
    """Test that CORS origins are configured."""
    assert isinstance(settings.cors_origins, list)
    assert len(settings.cors_origins) > 0
