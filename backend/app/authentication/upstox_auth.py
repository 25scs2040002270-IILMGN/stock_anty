import urllib.parse
from typing import Optional, Dict, Any
import httpx
from app.config.settings import settings
from app.database.connection import get_db


class UpstoxAuthManager:
    """
    Manages official Upstox OAuth 2.0 flow:
    - Authorization URL generation
    - Authorization code exchange for daily access token
    - Token storage in backend application_settings
    - Token validation via /v2/user/profile
    - Credentials auditing without exposing secrets to frontend
    """

    UPSTOX_AUTH_DIALOG_URL = "https://api.upstox.com/v2/login/authorization/dialog"
    UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
    UPSTOX_PROFILE_URL = "https://api.upstox.com/v2/user/profile"

    def __init__(self) -> None:
        self.db = get_db()
        self._cached_token: Optional[str] = None

    def get_credential_status(self) -> Dict[str, Any]:
        """
        Reports whether configuration credentials are set.
        Never exposes the actual secret or token values.
        """
        token = self.get_active_token()
        return {
            "has_api_key": bool(settings.UPSTOX_API_KEY.strip()),
            "has_api_secret": bool(settings.UPSTOX_API_SECRET.strip()),
            "has_redirect_uri": bool(settings.UPSTOX_REDIRECT_URI.strip()),
            "has_active_token": bool(token),
            "redirect_uri": settings.UPSTOX_REDIRECT_URI,
        }

    def generate_authorization_url(self) -> str:
        """
        Generates the official Upstox OAuth login URL.
        """
        if not settings.UPSTOX_API_KEY.strip():
            raise ValueError("UPSTOX_API_KEY is not configured on the backend.")
        if not settings.UPSTOX_REDIRECT_URI.strip():
            raise ValueError("UPSTOX_REDIRECT_URI is not configured on the backend.")

        params = {
            "response_type": "code",
            "client_id": settings.UPSTOX_API_KEY.strip(),
            "redirect_uri": settings.UPSTOX_REDIRECT_URI.strip(),
        }
        return f"{self.UPSTOX_AUTH_DIALOG_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchanges single-use authorization code for an Upstox access token.
        Stores the token securely in SQLite application_settings table.
        """
        if not code or not code.strip():
            raise ValueError("Authorization code is required.")
        if not settings.UPSTOX_API_KEY.strip():
            raise ValueError("UPSTOX_API_KEY is missing.")
        if not settings.UPSTOX_API_SECRET.strip():
            raise ValueError("UPSTOX_API_SECRET is missing.")

        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "code": code.strip(),
            "client_id": settings.UPSTOX_API_KEY.strip(),
            "client_secret": settings.UPSTOX_API_SECRET.strip(),
            "redirect_uri": settings.UPSTOX_REDIRECT_URI.strip(),
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.UPSTOX_TOKEN_URL, headers=headers, data=data)
            
            if resp.status_code != 200:
                error_msg = f"Token exchange failed with status {resp.status_code}: {resp.text}"
                self.db.log_connection_event("UPSTOX", "DISCONNECTED", "Token exchange failed", {"response": resp.text})
                raise RuntimeError(error_msg)
            
            token_data = resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise RuntimeError(f"No access_token found in Upstox response: {token_data}")

            # Store in DB and local cache
            self.set_active_token(access_token)
            
            user_name = token_data.get("user_name", "User")
            user_id = token_data.get("user_id", "")
            self.db.log_connection_event(
                "UPSTOX", "DISCONNECTED", f"Access token acquired for {user_name} ({user_id})",
                {"user_id": user_id, "user_name": user_name}
            )

            return {
                "success": True,
                "user_name": user_name,
                "user_id": user_id,
                "email": token_data.get("email", ""),
            }

    def set_active_token(self, token: str) -> None:
        """Stores token in database and in-memory cache."""
        self._cached_token = token.strip()
        self.db.set_setting("upstox_access_token", self._cached_token)

    def get_active_token(self) -> Optional[str]:
        """
        Retrieves current valid token:
        1. In-memory cache
        2. Database settings
        3. Environment variable UPSTOX_ACCESS_TOKEN
        """
        if self._cached_token:
            return self._cached_token
        
        db_token = self.db.get_setting("upstox_access_token")
        if db_token and db_token.strip():
            self._cached_token = db_token.strip()
            return self._cached_token

        if settings.UPSTOX_ACCESS_TOKEN and settings.UPSTOX_ACCESS_TOKEN.strip():
            self._cached_token = settings.UPSTOX_ACCESS_TOKEN.strip()
            return self._cached_token

        return None

    async def validate_token(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates the active token against Upstox /v2/user/profile.
        """
        tok = token or self.get_active_token()
        if not tok:
            return {"valid": False, "error": "No token available"}

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {tok}",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.UPSTOX_PROFILE_URL, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {
                        "valid": True,
                        "user_id": data.get("user_id"),
                        "user_name": data.get("user_name"),
                        "email": data.get("email"),
                    }
                else:
                    return {
                        "valid": False,
                        "status_code": resp.status_code,
                        "error": resp.text,
                    }
        except Exception as e:
            return {"valid": False, "error": str(e)}


_auth_instance: Optional[UpstoxAuthManager] = None


def get_auth_manager() -> UpstoxAuthManager:
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = UpstoxAuthManager()
    return _auth_instance

