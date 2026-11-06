import pytest
from app.authentication.upstox_auth import UpstoxAuthManager
from app.config.settings import settings


def test_missing_credentials_detection(temp_db, monkeypatch):
    """Verify that auth manager correctly detects and reports missing credentials."""
    monkeypatch.setattr(settings, "UPSTOX_API_KEY", "")
    monkeypatch.setattr(settings, "UPSTOX_API_SECRET", "")
    monkeypatch.setattr(settings, "UPSTOX_ACCESS_TOKEN", "")

    auth = UpstoxAuthManager()
    status = auth.get_credential_status()
    assert status["has_api_key"] is False
    assert status["has_api_secret"] is False
    assert status["has_active_token"] is False

    with pytest.raises(ValueError, match="UPSTOX_API_KEY is not configured"):
        auth.generate_authorization_url()


def test_authorization_url_generation(temp_db, monkeypatch):
    """Verify that official Upstox OAuth URL is properly formed with parameters."""
    monkeypatch.setattr(settings, "UPSTOX_API_KEY", "test_api_key_123")
    monkeypatch.setattr(settings, "UPSTOX_REDIRECT_URI", "http://localhost:8000/api/auth/callback")

    auth = UpstoxAuthManager()
    url = auth.generate_authorization_url()
    assert "https://api.upstox.com/v2/login/authorization/dialog" in url
    assert "client_id=test_api_key_123" in url
    assert "response_type=code" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fauth%2Fcallback" in url


def test_token_storage_and_retrieval(temp_db):
    """Verify storing access token securely in SQLite without exposing secrets."""
    auth = UpstoxAuthManager()
    assert auth.get_active_token() is None

    test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_token_payload"
    auth.set_active_token(test_token)

    assert auth.get_active_token() == test_token
    # Verify in DB
    db_val = temp_db.get_setting("upstox_access_token")
    assert db_val == test_token

