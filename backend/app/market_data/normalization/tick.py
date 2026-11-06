from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time
from app.utils.timezone import format_ist_datetime


class DepthLevel(BaseModel):
    price: float
    quantity: int
    orders: int = 0


class OHLCData(BaseModel):
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None


class MarketTick(BaseModel):
    """
    Standardized, broker-agnostic market event schema for MarketPulse AI.
    Normalizes feeds from Upstox, FYERS, etc. into a single unified format.
    """
    symbol: str = Field(..., description="Trading symbol, e.g. HDFCBANK, ICICIBANK")
    instrument_key: str = Field(..., description="Unique instrument key, e.g. NSE_EQ|INE040A01034")
    exchange: str = Field(default="NSE_EQ", description="Exchange code")
    ltp: float = Field(..., description="Last traded price")
    exchange_timestamp: int = Field(..., description="Exchange timestamp in milliseconds")
    exchange_datetime_ist: str = Field(default="", description="Human-readable timestamp in IST")
    last_traded_quantity: int = Field(default=0, description="Quantity traded in this transaction")
    cumulative_volume: int = Field(default=0, description="Cumulative day volume")
    ohlc: OHLCData = Field(default_factory=OHLCData, description="Daily/session OHLC if provided")
    bids: List[DepthLevel] = Field(default_factory=list, description="Top 5 bid levels")
    asks: List[DepthLevel] = Field(default_factory=list, description="Top 5 ask levels")
    received_at: int = Field(default_factory=lambda: int(time.time() * 1000), description="Local receive time in ms")
    provider: str = Field(default="UPSTOX", description="Market data provider name")
    data_status: str = Field(default="LIVE", description="Status: LIVE, DELAYED, STALE, DISCONNECTED")

    def model_post_init(self, __context: Any) -> None:
        if not self.exchange_datetime_ist and self.exchange_timestamp:
            self.exchange_datetime_ist = format_ist_datetime(self.exchange_timestamp)
        elif not self.exchange_datetime_ist:
            self.exchange_datetime_ist = format_ist_datetime(self.received_at)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

