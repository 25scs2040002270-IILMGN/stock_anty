from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from app.analysis.service import get_analysis_service
from app.database.connection import get_db
from app.config.settings import settings

router = APIRouter(prefix="/api", tags=["Analysis & Signals"])


class RiskSettingsUpdateRequest(BaseModel):
    trading_capital: float = Field(..., gt=0, description="Available personal trading capital in INR")
    risk_percentage: float = Field(..., gt=0, le=10, description="Max percentage risk per trade (e.g. 1.0 = 1%)")
    max_risk_reward_min: float = Field(default=1.5, ge=1.0, description="Minimum acceptable R:R ratio")
    lot_size: int = Field(default=1, ge=1, description="Lot size constraints (1 for NSE equity)")


@router.get("/analysis/HDFCBANK")
async def analyze_hdfcbank():
    """Executes multi-timeframe quantitative analysis and generates signals for HDFCBANK."""
    svc = get_analysis_service()
    res = await svc.run_analysis("HDFCBANK")
    return res.to_dict()


@router.get("/analysis/ICICIBANK")
async def analyze_icicibank():
    """Executes multi-timeframe quantitative analysis and generates signals for ICICIBANK."""
    svc = get_analysis_service()
    res = await svc.run_analysis("ICICIBANK")
    return res.to_dict()


@router.get("/signals")
async def get_active_signals(symbol: Optional[str] = Query(None, description="Filter by HDFCBANK or ICICIBANK")):
    """Returns currently ACTIVE analytical signals."""
    db = get_db()
    if symbol and symbol.upper() not in ("HDFCBANK", "ICICIBANK"):
        raise HTTPException(status_code=400, detail=f"Instrument '{symbol}' is not supported.")
    active = db.get_active_signals(symbol=symbol)
    return active


@router.get("/signals/history")
async def get_signals_history(
    symbol: Optional[str] = Query(None, description="Filter by HDFCBANK or ICICIBANK"),
    limit: int = Query(50, ge=1, le=200)
):
    """Returns historical signals and their invalidation/expiration reasons from SQLite."""
    db = get_db()
    if symbol and symbol.upper() not in ("HDFCBANK", "ICICIBANK"):
        raise HTTPException(status_code=400, detail=f"Instrument '{symbol}' is not supported.")
    history = db.get_signals_history(symbol=symbol, limit=limit)
    return history


@router.get("/indicators/{symbol}")
async def get_indicators_for_symbol(symbol: str = Path(..., description="Stock symbol (HDFCBANK or ICICIBANK)")):
    """Returns comprehensive technical indicators across 1m, 5m, and 15m timeframes."""
    sym = symbol.upper()
    if sym not in ("HDFCBANK", "ICICIBANK"):
        raise HTTPException(status_code=400, detail=f"Instrument '{symbol}' is not supported.")
    svc = get_analysis_service()
    try:
        data = svc.get_indicators_summary(sym)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/settings")
async def get_risk_settings():
    """Retrieves current risk parameters and capital configuration."""
    svc = get_analysis_service()
    return svc.get_risk_settings()


@router.post("/risk/settings")
async def update_risk_settings(req: RiskSettingsUpdateRequest):
    """Updates and persists personal risk parameters to SQLite."""
    svc = get_analysis_service()
    updated = svc.update_risk_settings(req.model_dump())
    return {"status": "success", "settings": updated}

