import asyncio
import json
import logging
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from app.market_data.normalization.tick import MarketTick
from app.database.models import CandleRecord
from app.market_data.connection.connection_manager import get_connection_manager
from app.database.connection import get_db

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    """
    Manages client WebSocket connections to /ws/market.
    Broadcasting live ticks, candle updates, and connection status.
    """

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.conn_manager = get_connection_manager()
        self.db = get_db()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Frontend client connected to /ws/market. Total active: {len(self.active_connections)}")

        # Send initial status snapshot immediately
        try:
            status_summary = self.conn_manager.get_status_summary()
            await websocket.send_json({
                "type": "status",
                "data": status_summary
            })

            # Send latest ticks for configured instruments
            latest_ticks = self.db.get_latest_ticks()
            for sym, tick in latest_ticks.items():
                await websocket.send_json({
                    "type": "tick",
                    "data": tick
                })
        except Exception as e:
            logger.error(f"Error sending initial snapshot to client: {e}")

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info(f"Frontend client disconnected. Remaining active: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Sends JSON payload to all connected frontend clients."""
        if not self.active_connections:
            return

        dead_connections: Set[WebSocket] = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to client: {e}")
                dead_connections.add(ws)

        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast_tick(self, tick: MarketTick) -> None:
        await self.broadcast({
            "type": "tick",
            "data": tick.to_dict()
        })

    async def broadcast_candle(self, candle: CandleRecord) -> None:
        await self.broadcast({
            "type": "candle",
            "data": candle.to_dict()
        })

    async def broadcast_status(self, status: Dict[str, Any]) -> None:
        await self.broadcast({
            "type": "status",
            "data": status
        })

    async def broadcast_message(self, msg_type: str, data: Any) -> None:
        await self.broadcast({
            "type": msg_type,
            "data": data
        })


_broadcaster: Optional[WebSocketBroadcaster] = None


def get_broadcaster() -> WebSocketBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = WebSocketBroadcaster()
    return _broadcaster

