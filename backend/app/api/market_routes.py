from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.database.connection import get_db
from app.market_data.connection.connection_manager import get_connection_manager
from app.market_data.providers.upstox_provider import get_upstox_provider
from app.websocket.server import get_broadcaster
from app.utils.timezone import get_ist_now, format_ist_datetime, is_market_session_open

router = APIRouter(prefix="/api/market", tags=["Market Data"])
broadcaster = get_broadcaster()
db = get_db()
conn_manager = get_connection_manager()


# ----------------------------------------------------
# Response Schemas
# ----------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    app_env: str
    market_open: bool
    current_time_ist: str
    supported_instruments: List[str]
    forbidden_instruments_enforced: bool


class MarketStatusResponse(BaseModel):
    provider: str
    state: str
    is_socket_connected: bool
    subscribed_instruments: List[str]
    subscription_count: int
    reconnect_count: int
    last_tick_time_sec_ago: Optional[float]
    last_exchange_datetime_ist: Optional[str]
    is_market_session_open: bool
    evaluated_at: str


class InstrumentItem(BaseModel):
    instrument_key: str
    trading_symbol: str
    exchange: str
    segment: str
    instrument_type: str
    tick_size: float
    lot_size: int
    is_active: bool
    resolved_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ----------------------------------------------------
# API Endpoints
# ----------------------------------------------------
@router.get("/status", response_model=MarketStatusResponse)
async def get_market_status():
    """Returns real-time connection status and data freshness metrics."""
    return conn_manager.get_status_summary()


@router.get("/instruments", response_model=List[InstrumentItem])
async def get_instruments():
    """Returns resolved instruments stored in SQLite."""
    items = db.get_instruments(active_only=True)
    return [
        InstrumentItem(
            instrument_key=item["instrument_key"],
            trading_symbol=item["trading_symbol"],
            exchange=item["exchange"],
            segment=item["segment"],
            instrument_type=item["instrument_type"],
            tick_size=item["tick_size"],
            lot_size=item["lot_size"],
            is_active=bool(item["is_active"]),
            resolved_at=item["resolved_at"],
            metadata=item.get("metadata", {})
        )
        for item in items
    ]


@router.get("/latest")
async def get_latest_market_data():
    """Returns the most recent tick for each configured symbol."""
    return db.get_latest_ticks()


@router.get("/candles")
async def get_candles(
    symbol: str = Query(..., description="Trading symbol, e.g. HDFCBANK or ICICIBANK"),
    timeframe: str = Query("1m", pattern="^(1m|5m|15m)$", description="Candle timeframe"),
    limit: int = Query(200, ge=1, le=1000, description="Maximum candles to return")
):
    """Returns historical / recent candles constructed from market ticks."""
    sym = symbol.upper()
    if sym not in settings.ALLOWED_INSTRUMENTS_SET:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{sym}' is not supported. Only HDFCBANK and ICICIBANK are permitted."
        )

    candles = db.get_candles(sym, timeframe=timeframe, limit=limit)
    return {
        "symbol": sym,
        "timeframe": timeframe,
        "count": len(candles),
        "candles": candles
    }


@router.get("/logs")
async def get_connection_logs(
    limit: int = Query(50, ge=1, le=500, description="Log entries count")
):
    """Returns historical connection logs from SQLite."""
    return db.get_connection_logs(limit=limit)
