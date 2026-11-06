from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.authentication.upstox_auth import get_auth_manager
from app.market_data.providers.upstox_provider import get_upstox_provider

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
auth_mgr = get_auth_manager()


class TokenManualRequest(BaseModel):
    token: str = Field(..., description="Upstox daily access token")


@router.get("/status")
async def get_auth_status():
    """Returns credentials configuration status without revealing secrets."""
    status = auth_mgr.get_credential_status()
    # Check if active token is valid with Upstox API
    validation = await auth_mgr.validate_token()
    status["token_valid"] = validation.get("valid", False)
    if validation.get("valid"):
        status["user_name"] = validation.get("user_name")
        status["user_id"] = validation.get("user_id")
    else:
        status["validation_error"] = validation.get("error")
    return status


@router.get("/login-url")
async def get_login_url():
    """Generates the official Upstox OAuth authorization dialog URL."""
    try:
        url = auth_mgr.generate_authorization_url()
        return {"login_url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def auth_callback(
    code: Optional[str] = Query(None, description="Upstox OAuth authorization code"),
    error: Optional[str] = Query(None, description="OAuth error if any")
):
    """
    Handles OAuth callback from Upstox.
    Exchanges code for access token and stores it securely.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error from Upstox: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    try:
        result = await auth_mgr.exchange_code_for_token(code)
        # Attempt to reconnect market provider with the fresh token
        provider = get_upstox_provider()
        await provider.disconnect()
        await provider.connect()
        return {
            "status": "success",
            "message": "Authorization successful and access token acquired.",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange authorization code: {e}")


@router.post("/token")
async def set_manual_token(req: TokenManualRequest):
    """Allows setting a daily access token directly."""
    if not req.token or not req.token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty.")

    auth_mgr.set_active_token(req.token)
    validation = await auth_mgr.validate_token(req.token)
    
    if validation.get("valid"):
        # Reconnect provider with new token
        provider = get_upstox_provider()
        await provider.disconnect()
        await provider.connect()
        return {
            "status": "success",
            "message": "Token accepted and validated successfully.",
            "user": validation
        }
    else:
        return {
            "status": "warning",
            "message": "Token was saved but Upstox profile validation failed.",
            "details": validation
        }

