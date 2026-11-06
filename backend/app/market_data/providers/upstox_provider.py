import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional
import httpx
import websockets

from app.authentication.upstox_auth import get_auth_manager
from app.candles.engine import get_candle_engine
from app.config.settings import settings
from app.database.connection import get_db
from app.market_data.connection.connection_manager import get_connection_manager
from app.market_data.normalization.tick import DepthLevel, MarketTick, OHLCData
from app.market_data.protobuf import decode_feed_response
from app.market_data.providers.base import (
    BaseMarketDataProvider,
    ConnectionState,
    StateCallback,
    TickCallback,
)
from app.market_data.providers.upstox_instrument_resolver import get_instrument_resolver

logger = logging.getLogger(__name__)


class UpstoxMarketDataProvider(BaseMarketDataProvider):
    """
    Official Upstox Market Data Feed V3 Provider.
    Streams real-time market data over WebSockets using binary Protocol Buffers.
    Handles:
    - V3 Market Data Feed authorization (authorizedRedirectUri)
    - Full market depth and tick normalization
    - Auto-reconnection with exponential backoff
    - Staleness detection and state transitions
    - Integration with SQLite persistence and the Real-time Candle Engine
    """

    UPSTOX_V3_AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

    def __init__(self) -> None:
        self.auth_manager = get_auth_manager()
        self.conn_manager = get_connection_manager()
        self.candle_engine = get_candle_engine()
        self.resolver = get_instrument_resolver()
        self.db = get_db()

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running: bool = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._tick_callbacks: List[TickCallback] = []
        self._state_callbacks: List[StateCallback] = []

        # Key-to-symbol lookup: "NSE_EQ|INE040A01034" -> "HDFCBANK"
        self._key_to_symbol: Dict[str, str] = {}
        self._symbol_to_key: Dict[str, str] = {}

    def get_provider_name(self) -> str:
        return "UPSTOX"

    def set_tick_callback(self, callback: TickCallback) -> None:
        self._tick_callbacks.append(callback)

    def set_state_callback(self, callback: StateCallback) -> None:
        self._state_callbacks.append(callback)
        self.conn_manager.register_state_callback(callback)

    def get_connection_state(self) -> ConnectionState:
        return self.conn_manager.current_state

    async def initialize_instruments(self) -> None:
        """Resolves official instrument keys and initializes lookup mappings."""
        resolved = await self.resolver.resolve_instruments()
        for sym, rec in resolved.items():
            self._key_to_symbol[rec.instrument_key] = sym
            self._symbol_to_key[sym] = rec.instrument_key
        logger.info(f"Initialized Upstox instrument map: {self._key_to_symbol}")

    async def get_authorized_ws_url(self) -> str:
        """Fetches temporary authorized WebSocket redirect URI from Upstox API V3."""
        token = self.auth_manager.get_active_token()
        if not token:
            raise RuntimeError("Cannot authorize market feed: No active Upstox access token.")

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.UPSTOX_V3_AUTHORIZE_URL, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Failed to authorize Upstox V3 Market Data Feed ({resp.status_code}): {resp.text}"
                )
            
            data = resp.json().get("data", {})
            authorized_uri = data.get("authorizedRedirectUri")
            if not authorized_uri:
                raise RuntimeError(f"No authorizedRedirectUri returned: {resp.text}")
            
            return authorized_uri

    async def connect(self) -> None:
        """Starts the market data feed consumer loop."""
        if self._running:
            logger.warning("UpstoxMarketDataProvider is already running.")
            return

        self._running = True
        await self.conn_manager.start_watchdog()
        self._consumer_task = asyncio.create_task(self._connection_loop())

    async def disconnect(self) -> None:
        """Gracefully terminates WebSocket connection and watchdog."""
        self._running = False
        await self.conn_manager.stop_watchdog()

        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")
            self._ws = None

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        await self.conn_manager.update_socket_status(False, "Explicit disconnect")
        logger.info("UpstoxMarketDataProvider disconnected successfully.")

    async def _connection_loop(self) -> None:
        """Main loop managing connection, subscription, decoding, and auto-reconnection."""
        backoff_seconds = 2.0
        max_backoff = 30.0

        while self._running:
            try:
                # Ensure instruments are resolved
                if not self._key_to_symbol:
                    await self.initialize_instruments()

                logger.info("Authorizing Upstox V3 Market Data Feed...")
                ws_url = await self.get_authorized_ws_url()

                logger.info(f"Connecting to Upstox WebSocket...")
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    max_size=10 * 1024 * 1024  # 10MB max frame
                ) as ws:
                    self._ws = ws
                    backoff_seconds = 2.0  # Reset backoff upon successful connection
                    await self.conn_manager.update_socket_status(True, "Handshake complete")
                    
                    # Subscribe to configured instruments
                    await self._send_subscriptions(list(self._key_to_symbol.keys()))

                    # Process incoming binary frames
                    async for message in ws:
                        if not self._running:
                            break
                        if isinstance(message, bytes):
                            await self._handle_binary_message(message)
                        elif isinstance(message, str):
                            # Control / JSON responses from Upstox
                            logger.debug(f"Received JSON frame from Upstox WS: {message}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.conn_manager.reconnect_count += 1
                logger.error(f"Upstox WebSocket error: {e}. Reconnecting in {backoff_seconds}s...")
                await self.conn_manager.update_socket_status(False, f"Error: {e}")
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 1.5, max_backoff)

    async def _send_subscriptions(self, keys: List[str], mode: str = "full") -> None:
        """Sends subscription JSON payload over WebSocket."""
        if not self._ws or not keys:
            return

        new_keys = self.conn_manager.record_subscription(keys)
        if not new_keys:
            return

        sub_payload = {
            "guid": str(uuid.uuid4()),
            "method": "sub",
            "data": {
                "mode": mode,
                "instrumentKeys": new_keys
            }
        }
        await self._ws.send(json.dumps(sub_payload))
        logger.info(f"Subscribed to {len(new_keys)} instruments in mode '{mode}': {new_keys}")

    async def subscribe(self, instrument_keys: List[str], mode: str = "full") -> None:
        await self._send_subscriptions(instrument_keys, mode)

    async def unsubscribe(self, instrument_keys: List[str]) -> None:
        if not self._ws or not instrument_keys:
            return

        self.conn_manager.record_unsubscription(instrument_keys)
        unsub_payload = {
            "guid": str(uuid.uuid4()),
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        await self._ws.send(json.dumps(unsub_payload))
        logger.info(f"Unsubscribed from instruments: {instrument_keys}")

    async def _handle_binary_message(self, data: bytes) -> None:
        """Decodes Protobuf binary payload and normalizes market ticks."""
        try:
            feed_response = decode_feed_response(data)
        except Exception as e:
            logger.error(f"Failed to decode Protobuf feed response: {e}")
            return

        # Upstox feed response has a map: feeds[instrument_key] = Feed
        for inst_key, feed in feed_response.feeds.items():
            symbol = self._key_to_symbol.get(inst_key)
            if not symbol:
                # If key wasn't in cache, check if it matches a known symbol
                continue

            # Extract full feed or ltpc
            market_tick = self._normalize_protobuf_feed(inst_key, symbol, feed)
            if market_tick:
                # Update connection manager freshness
                self.conn_manager.record_tick_received(market_tick.exchange_timestamp)
                
                # Persist tick to SQLite
                self.db.save_tick(market_tick.to_dict())

                # Pass to real-time candle engine
                await self.candle_engine.process_tick(market_tick)

                # Broadcast to application listeners
                for cb in self._tick_callbacks:
                    try:
                        await cb(market_tick)
                    except Exception as e:
                        logger.error(f"Error in tick callback: {e}")

    def _normalize_protobuf_feed(self, inst_key: str, symbol: str, feed) -> Optional[MarketTick]:
        """Maps Upstox Protobuf Feed structure into our provider-independent MarketTick."""
        try:
            ltp = 0.0
            ltt = int(time.time() * 1000)
            ltq = 0
            vtt = 0
            ohlc_obj = OHLCData()
            bids: List[DepthLevel] = []
            asks: List[DepthLevel] = []

            # Check if fullFeed or ltpc is present
            if feed.HasField("fullFeed"):
                full = feed.fullFeed
                if full.HasField("marketFF"):
                    mff = full.marketFF
                    if mff.HasField("ltpc"):
                        ltp = mff.ltpc.ltp
                        ltt = mff.ltpc.ltt or ltt
                        ltq = mff.ltpc.ltq
                        if mff.ltpc.cp:
                            ohlc_obj.close = mff.ltpc.cp

                    vtt = mff.vtt

                    # OHLC
                    if mff.HasField("marketOHLC") and mff.marketOHLC.ohlc:
                        first_ohlc = mff.marketOHLC.ohlc[0]
                        ohlc_obj.open = first_ohlc.open
                        ohlc_obj.high = first_ohlc.high
                        ohlc_obj.low = first_ohlc.low
                        ohlc_obj.close = first_ohlc.close

                    # Market depth (bids / asks)
                    if mff.HasField("marketLevel"):
                        for q in mff.marketLevel.bidAskQuote:
                            if q.bidP > 0:
                                bids.append(DepthLevel(price=q.bidP, quantity=q.bidQ, orders=q.bidOrders))
                            if q.askP > 0:
                                asks.append(DepthLevel(price=q.askP, quantity=q.askQ, orders=q.askOrders))

            elif feed.HasField("ltpc"):
                ltpc = feed.ltpc
                ltp = ltpc.ltp
                ltt = ltpc.ltt or ltt
                ltq = ltpc.ltq
                if ltpc.cp:
                    ohlc_obj.close = ltpc.cp

            if ltp <= 0.0:
                return None

            return MarketTick(
                symbol=symbol,
                instrument_key=inst_key,
                exchange="NSE_EQ",
                ltp=ltp,
                exchange_timestamp=ltt,
                last_traded_quantity=ltq,
                cumulative_volume=vtt,
                ohlc=ohlc_obj,
                bids=bids[:5],
                asks=asks[:5],
                received_at=int(time.time() * 1000),
                provider="UPSTOX",
                data_status="LIVE"
            )

        except Exception as e:
            logger.error(f"Error normalizing Protobuf feed for {symbol}: {e}")
            return None


_provider_instance: Optional[UpstoxMarketDataProvider] = None


def get_upstox_provider() -> UpstoxMarketDataProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = UpstoxMarketDataProvider()
    return _provider_instance

