from enum import Enum
from abc import ABC, abstractmethod
from typing import List, Callable, Coroutine, Any, Optional
from app.market_data.normalization.tick import MarketTick


class ConnectionState(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"


TickCallback = Callable[[MarketTick], Coroutine[Any, Any, None]]
StateCallback = Callable[[ConnectionState, str], Coroutine[Any, Any, None]]


class BaseMarketDataProvider(ABC):
    """
    Abstract interface for all Market Data Providers (Upstox, FYERS, etc.).
    Ensures that candle engine, storage, and frontend remain completely agnostic
    of the underlying broker or feed mechanism.
    """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the identifier of the provider, e.g. UPSTOX."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """Establishes connection to the market data feed."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully closes the feed connection."""
        pass

    @abstractmethod
    async def subscribe(self, instrument_keys: List[str], mode: str = "full") -> None:
        """Subscribes to market updates for the specified instrument keys."""
        pass

    @abstractmethod
    async def unsubscribe(self, instrument_keys: List[str]) -> None:
        """Unsubscribes from the specified instruments."""
        pass

    @abstractmethod
    def get_connection_state(self) -> ConnectionState:
        """Returns the current evaluated connection state (LIVE, DELAYED, STALE, DISCONNECTED)."""
        pass

    @abstractmethod
    def set_tick_callback(self, callback: TickCallback) -> None:
        """Registers a callback invoked upon every normalized MarketTick."""
        pass

    @abstractmethod
    def set_state_callback(self, callback: StateCallback) -> None:
        """Registers a callback invoked when connection state changes."""
        pass

