import logging
import time
from collections import deque
from typing import Dict, List, Optional, Tuple, Callable, Coroutine, Any
from app.database.connection import get_db
from app.database.models import CandleRecord
from app.market_data.normalization.tick import MarketTick
from app.utils.timezone import to_ist, format_ist_datetime

logger = logging.getLogger(__name__)

CandleCallback = Callable[[CandleRecord], Coroutine[Any, Any, None]]

TIMEFRAMES = {
    "1m": 60,
    "5m": 300,
    "15m": 900
}


class CandleEngine:
    """
    Real-time OHLCV Candle Construction Engine.
    Builds 1-minute, 5-minute, and 15-minute candles from normalized MarketTicks.
    Features:
    - Precise epoch boundary math
    - Deduplication of incoming ticks
    - Proper volume calculation (cumulative-volume difference or verified LTQ)
    - Session reset handling
    - Forming candle updates vs. finalized completed candles
    - Strict avoidance of fabricated/synthetic candles
    - Asia/Kolkata timezone formatting
    """

    def __init__(self) -> None:
        self.db = get_db()
        # Active forming candles: key = (symbol, timeframe) -> CandleRecord
        self.active_candles: Dict[Tuple[str, str], CandleRecord] = {}
        
        # State tracking for volume calculation & deduplication:
        # symbol -> last_seen_cumulative_volume
        self.last_cumulative_volumes: Dict[str, int] = {}
        # symbol -> last_exchange_timestamp
        self.last_exchange_timestamps: Dict[str, int] = {}
        # symbol -> deque of recent tick signatures (timestamp_ms, ltp, ltq)
        self.recent_ticks_cache: Dict[str, deque] = {}

        self.candle_callbacks: List[CandleCallback] = []

    def register_candle_callback(self, callback: CandleCallback) -> None:
        self.candle_callbacks.append(callback)

    def _is_duplicate_tick(self, tick: MarketTick) -> bool:
        """Checks if this exact tick was already processed."""
        sym = tick.symbol
        if sym not in self.recent_ticks_cache:
            self.recent_ticks_cache[sym] = deque(maxlen=200)

        tick_sig = (tick.exchange_timestamp, round(tick.ltp, 4), tick.last_traded_quantity)
        if tick_sig in self.recent_ticks_cache[sym]:
            return True

        self.recent_ticks_cache[sym].append(tick_sig)
        return False

    def _calculate_tick_volume(self, tick: MarketTick) -> int:
        """
        Calculates the volume for the current tick without using cumulative day volume
        as a single tick's volume.
        """
        sym = tick.symbol
        last_cum_vol = self.last_cumulative_volumes.get(sym, 0)
        curr_cum_vol = tick.cumulative_volume

        volume_for_tick = 0

        if curr_cum_vol > 0:
            if last_cum_vol == 0:
                # First tick received: use tick's LTQ if available, or initialize baseline
                volume_for_tick = tick.last_traded_quantity if tick.last_traded_quantity > 0 else 0
                self.last_cumulative_volumes[sym] = curr_cum_vol
            elif curr_cum_vol >= last_cum_vol:
                # Cumulative volume increased: difference is the actual volume traded
                volume_for_tick = curr_cum_vol - last_cum_vol
                self.last_cumulative_volumes[sym] = curr_cum_vol
            else:
                # Cumulative volume reset (e.g. new session / new trading day)
                volume_for_tick = tick.last_traded_quantity if tick.last_traded_quantity > 0 else 0
                self.last_cumulative_volumes[sym] = curr_cum_vol
        elif tick.last_traded_quantity > 0:
            volume_for_tick = tick.last_traded_quantity

        return max(0, volume_for_tick)

    async def process_tick(self, tick: MarketTick) -> List[CandleRecord]:
        """
        Processes an incoming normalized market tick across all configured timeframes (1m, 5m, 15m).
        Returns the list of updated/finalized candles.
        """
        # Deduplication check
        if self._is_duplicate_tick(tick):
            logger.debug(f"Duplicate tick ignored for {tick.symbol} at {tick.exchange_timestamp}")
            return []

        # Calculate genuine delta volume
        tick_volume = self._calculate_tick_volume(tick)

        # Exchange timestamp in seconds
        ts_ms = tick.exchange_timestamp or tick.received_at
        ts_sec = ts_ms // 1000

        updated_candles: List[CandleRecord] = []

        for tf, interval_sec in TIMEFRAMES.items():
            candle = await self._aggregate_for_timeframe(
                tick=tick,
                timeframe=tf,
                interval_sec=interval_sec,
                ts_sec=ts_sec,
                tick_volume=tick_volume
            )
            if candle:
                updated_candles.append(candle)

        return updated_candles

    async def _aggregate_for_timeframe(
        self,
        tick: MarketTick,
        timeframe: str,
        interval_sec: int,
        ts_sec: int,
        tick_volume: int
    ) -> Optional[CandleRecord]:
        """Aggregates a tick into a specific timeframe bucket."""
        key = (tick.symbol, timeframe)
        
        # Calculate standard epoch interval boundary
        bucket_open_time = (ts_sec // interval_sec) * interval_sec
        bucket_close_time = bucket_open_time + interval_sec

        active = self.active_candles.get(key)

        if active is None:
            # First candle for this symbol & timeframe
            new_candle = CandleRecord(
                instrument_key=tick.instrument_key,
                symbol=tick.symbol,
                timeframe=timeframe,
                open_time=bucket_open_time,
                close_time=bucket_close_time,
                open_datetime_ist=format_ist_datetime(bucket_open_time),
                open=tick.ltp,
                high=tick.ltp,
                low=tick.ltp,
                close=tick.ltp,
                volume=tick_volume,
                is_complete=False,
                created_at=int(time.time()),
                updated_at=int(time.time())
            )
            self.active_candles[key] = new_candle
            self.db.save_or_update_candle(new_candle)
            await self._notify_callbacks(new_candle)
            return new_candle

        if bucket_open_time == active.open_time:
            # Update currently forming candle
            active.high = max(active.high, tick.ltp)
            active.low = min(active.low, tick.ltp)
            active.close = tick.ltp
            active.volume += tick_volume
            active.updated_at = int(time.time())
            
            self.db.save_or_update_candle(active)
            await self._notify_callbacks(active)
            return active

        elif bucket_open_time > active.open_time:
            # Finalize previous candle!
            active.is_complete = True
            active.updated_at = int(time.time())
            self.db.save_or_update_candle(active)
            await self._notify_callbacks(active)
            logger.info(f"Finalized {timeframe} candle for {tick.symbol} at {active.open_datetime_ist}")

            # Start fresh forming candle
            new_candle = CandleRecord(
                instrument_key=tick.instrument_key,
                symbol=tick.symbol,
                timeframe=timeframe,
                open_time=bucket_open_time,
                close_time=bucket_close_time,
                open_datetime_ist=format_ist_datetime(bucket_open_time),
                open=tick.ltp,
                high=tick.ltp,
                low=tick.ltp,
                close=tick.ltp,
                volume=tick_volume,
                is_complete=False,
                created_at=int(time.time()),
                updated_at=int(time.time())
            )
            self.active_candles[key] = new_candle
            self.db.save_or_update_candle(new_candle)
            await self._notify_callbacks(new_candle)
            return new_candle

        else:
            # Out-of-order tick for an older bucket
            logger.warning(
                f"Out-of-order tick for {tick.symbol} {timeframe}: bucket {bucket_open_time} < active {active.open_time}"
            )
            # Update historical candle in SQLite without displacing active forming candle
            # Fetch existing candle record from database if present
            existing_rows = self.db.get_candles(tick.symbol, timeframe=timeframe, limit=20)
            for r in existing_rows:
                if r["open_time"] == bucket_open_time:
                    updated_c = CandleRecord(
                        instrument_key=tick.instrument_key,
                        symbol=tick.symbol,
                        timeframe=timeframe,
                        open_time=bucket_open_time,
                        close_time=bucket_close_time,
                        open_datetime_ist=format_ist_datetime(bucket_open_time),
                        open=r["open"],
                        high=max(r["high"], tick.ltp),
                        low=min(r["low"], tick.ltp),
                        close=r["close"],
                        volume=r["volume"] + tick_volume,
                        is_complete=bool(r["is_complete"])
                    )
                    self.db.save_or_update_candle(updated_c)
                    return updated_c
            return None

    async def _notify_callbacks(self, candle: CandleRecord) -> None:
        for cb in self.candle_callbacks:
            try:
                await cb(candle)
            except Exception as e:
                logger.error(f"Error in candle callback: {e}")


_engine_instance: Optional[CandleEngine] = None


def get_candle_engine() -> CandleEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CandleEngine()
    return _engine_instance

