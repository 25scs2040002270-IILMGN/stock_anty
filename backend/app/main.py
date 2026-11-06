import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.api.market_routes import router as market_router, HealthResponse
from app.api.auth_routes import router as auth_router
from app.api.analysis_routes import router as analysis_router
from app.api.backtest_routes import router as backtest_router
from app.analysis.service import get_analysis_service
from app.market_data.providers.upstox_provider import get_upstox_provider
from app.market_data.providers.upstox_instrument_resolver import get_instrument_resolver
from app.candles.engine import get_candle_engine
from app.websocket.server import get_broadcaster
from app.utils.timezone import get_ist_now, format_ist_datetime, is_market_session_open

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("marketpulse.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes instruments and background market streaming."""
    logger.info("Initializing MarketPulse AI Backend...")
    
    resolver = get_instrument_resolver()
    provider = get_upstox_provider()
    candle_engine = get_candle_engine()
    broadcaster = get_broadcaster()

    # Resolve official instruments (HDFCBANK, ICICIBANK)
    try:
        resolved = await resolver.resolve_instruments()
        logger.info(f"Resolved instruments: {list(resolved.keys())}")
    except Exception as e:
        logger.error(f"Failed to resolve instruments during startup: {e}")

    # Wire event pipelines
    provider.set_tick_callback(broadcaster.broadcast_tick)
    candle_engine.register_candle_callback(broadcaster.broadcast_candle)

    analysis_service = get_analysis_service()
    candle_engine.register_candle_callback(analysis_service.on_candle_completed)

    async def on_state_change(new_state, msg):
        status_data = provider.conn_manager.get_status_summary()
        await broadcaster.broadcast_status(status_data)

    provider.set_state_callback(on_state_change)

    # If an access token is already available, start provider in background
    if provider.auth_manager.get_active_token():
        logger.info("Upstox access token detected. Starting market feed connection...")
        asyncio.create_task(provider.connect())
    else:
        logger.warning(
            "No Upstox access token found at startup. Feed is waiting for authentication via /api/auth."
        )

    yield

    logger.info("Shutting down MarketPulse AI Backend...")
    await provider.disconnect()


app = FastAPI(
    title="MarketPulse AI Backend",
    version="1.0.0",
    description="High-frequency personal stock market analysis infrastructure for HDFCBANK & ICICIBANK.",
    lifespan=lifespan
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_ORIGIN,
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(market_router)
app.include_router(auth_router)
app.include_router(analysis_router)
app.include_router(backtest_router)


# ----------------------------------------------------
# Global Health Check Endpoints
# ----------------------------------------------------
@app.get("/", tags=["Root"])
@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint providing runtime state and market session status."""
    return HealthResponse(
        status="healthy",
        app_env=settings.APP_ENV,
        market_open=is_market_session_open(),
        current_time_ist=format_ist_datetime(get_ist_now()),
        supported_instruments=settings.instruments_list,
        forbidden_instruments_enforced=True
    )


# ----------------------------------------------------
# WebSocket Endpoint
# ----------------------------------------------------
@app.websocket("/ws/market")
async def market_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for frontend clients to stream live ticks,
    forming/finalized candles, and connection status.
    """
    broadcaster = get_broadcaster()
    await broadcaster.connect(websocket)
    try:
        while True:
            # Keep socket alive and receive client pings/messages
            data = await websocket.receive_text()
            # Respond to client ping
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception as e:
        logger.debug(f"Client websocket exception: {e}")
        broadcaster.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

