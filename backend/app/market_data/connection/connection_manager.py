import asyncio
import logging
import time
from typing import Dict, Optional, Set, Callable, Coroutine, Any, List
from app.config.settings import settings
from app.database.connection import get_db
from app.market_data.providers.base import ConnectionState, StateCallback
from app.utils.timezone import is_market_session_open, get_ist_now, format_ist_datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Supervises WebSocket connection health and market data freshness:
    - Tracks raw socket connection vs. actual market data freshness
    - Evaluates connection state (LIVE, DELAYED, STALE, DISCONNECTED)
    - Staleness detector: marks STALE if no updates received within threshold
    - Duplicate subscription tracker
    - Reconnection backoff manager
    - Logs state transitions to SQLite connection_logs
    """

    def __init__(self, provider_name: str = "UPSTOX") -> None:
        self.provider_name = provider_name
        self.db = get_db()
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self.is_socket_connected: bool = False
        self.last_tick_received_at: float = 0.0
        self.last_exchange_timestamp: int = 0
        self.subscribed_keys: Set[str] = set()
        self.reconnect_count: int = 0
        self.watchdog_task: Optional[asyncio.Task] = None
        self.state_callbacks: List[StateCallback] = []

    def register_state_callback(self, callback: StateCallback) -> None:
        self.state_callbacks.append(callback)

    @property
    def current_state(self) -> ConnectionState:
        return self._state

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides a complete status overview of provider connectivity."""
        now = time.time()
        time_since_last_tick = (now - self.last_tick_received_at) if self.last_tick_received_at > 0 else None
        
        return {
            "provider": self.provider_name,
            "state": self._state.value,
            "is_socket_connected": self.is_socket_connected,
            "subscribed_instruments": list(self.subscribed_keys),
            "subscription_count": len(self.subscribed_keys),
            "reconnect_count": self.reconnect_count,
            "last_tick_time_sec_ago": round(time_since_last_tick, 1) if time_since_last_tick is not None else None,
            "last_exchange_datetime_ist": format_ist_datetime(self.last_exchange_timestamp) if self.last_exchange_timestamp > 0 else None,
            "is_market_session_open": is_market_session_open(),
            "evaluated_at": format_ist_datetime(get_ist_now()),
        }

    async def update_socket_status(self, connected: bool, reason: str = "") -> None:
        """Called when WebSocket connects or disconnects."""
        self.is_socket_connected = connected
        if not connected:
            self.last_tick_received_at = 0.0
            await self._set_state(ConnectionState.DISCONNECTED, f"Socket disconnected: {reason}")
        else:
            # Initially STALE until first valid market tick arrives
            await self._set_state(ConnectionState.STALE, f"Socket connected ({reason}), awaiting initial market updates")

    def record_tick_received(self, exchange_timestamp_ms: int) -> None:
        """Called upon receiving a valid market tick."""
        self.last_tick_received_at = time.time()
        if exchange_timestamp_ms > self.last_exchange_timestamp:
            self.last_exchange_timestamp = exchange_timestamp_ms

    def record_subscription(self, keys: List[str]) -> List[str]:
        """
        Adds keys to subscription list and returns only newly added keys
        to prevent duplicate subscription frames over the wire.
        """
        new_keys = []
        for k in keys:
            if k not in self.subscribed_keys:
                self.subscribed_keys.add(k)
                new_keys.append(k)
            else:
                logger.info(f"Duplicate subscription prevented for key: {k}")
        return new_keys

    def record_unsubscription(self, keys: List[str]) -> None:
        for k in keys:
            self.subscribed_keys.discard(k)

    async def evaluate_freshness(self) -> ConnectionState:
        """
        Evaluates whether data is genuinely LIVE, DELAYED, STALE, or DISCONNECTED.
        Strictly enforces:
        - If socket disconnected -> DISCONNECTED
        - If no recent valid ticks within threshold -> STALE
        - If exchange timestamp significantly lags current wall clock -> DELAYED
        - Only marked LIVE if recent ticks received and socket connected
        """
        if not self.is_socket_connected:
            return ConnectionState.DISCONNECTED

        now = time.time()
        time_since_tick = now - self.last_tick_received_at if self.last_tick_received_at > 0 else 999999

        threshold = settings.STALE_DATA_THRESHOLD_SECONDS

        if time_since_tick > threshold:
            return ConnectionState.STALE

        # Check if exchange timestamp is significantly delayed (> 20 seconds behind wall clock)
        if self.last_exchange_timestamp > 0:
            ex_sec = self.last_exchange_timestamp / 1000.0
            if (now - ex_sec) > 30.0:
                return ConnectionState.DELAYED

        return ConnectionState.LIVE

    async def _set_state(self, new_state: ConnectionState, message: str) -> None:
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.info(f"Connection state changed: {old_state.value} -> {new_state.value} ({message})")
            
            # Log transition to database
            self.db.log_connection_event(
                provider=self.provider_name,
                state=new_state.value,
                message=message,
                details={"old_state": old_state.value, "new_state": new_state.value}
            )

            # Notify listeners
            for cb in self.state_callbacks:
                try:
                    await cb(new_state, message)
                except Exception as e:
                    logger.error(f"Error in state callback: {e}")

    async def start_watchdog(self) -> None:
        """Periodic background task that monitors data staleness and connection status."""
        if self.watchdog_task and not self.watchdog_task.done():
            return
        self.watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def stop_watchdog(self) -> None:
        if self.watchdog_task:
            self.watchdog_task.cancel()
            try:
                await self.watchdog_task
            except asyncio.CancelledError:
                pass
            self.watchdog_task = None

    async def _watchdog_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(2.0)
                evaluated = await self.evaluate_freshness()
                if evaluated != self._state:
                    await self._set_state(
                        evaluated,
                        f"Watchdog evaluation: state changed to {evaluated.value}"
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection watchdog: {e}")
                await asyncio.sleep(5.0)


_conn_mgr: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    global _conn_mgr
    if _conn_mgr is None:
        _conn_mgr = ConnectionManager()
    return _conn_mgr

