import asyncio
import pytest
from app.candles.engine import CandleEngine
from app.market_data.normalization.tick import MarketTick


def test_candle_construction_and_boundaries(temp_db):
    """Verify that candles construct OHLC correctly within standard interval boundaries."""
    async def _test():
        engine = CandleEngine()

        # Base timestamp: 10:00:15 IST (epoch seconds: 1730800815)
        base_ts_sec = 1730800815
        base_ts_ms = base_ts_sec * 1000

        # Tick 1 at 10:00:15
        tick1 = MarketTick(
            symbol="HDFCBANK",
            instrument_key="NSE_EQ|INE040A01034",
            ltp=1520.0,
            exchange_timestamp=base_ts_ms,
            last_traded_quantity=50,
            cumulative_volume=100000
        )
        candles = await engine.process_tick(tick1)
        assert len(candles) == 3  # 1m, 5m, 15m

        c_1m = [c for c in candles if c.timeframe == "1m"][0]
        assert c_1m.open == 1520.0
        assert c_1m.high == 1520.0
        assert c_1m.low == 1520.0
        assert c_1m.close == 1520.0
        assert c_1m.open_time == (base_ts_sec // 60) * 60
        assert c_1m.close_time == c_1m.open_time + 60
        assert c_1m.is_complete is False

        # Tick 2 at 10:00:30 (higher price, volume increases by 100)
        tick2 = MarketTick(
            symbol="HDFCBANK",
            instrument_key="NSE_EQ|INE040A01034",
            ltp=1525.0,
            exchange_timestamp=base_ts_ms + 15000,
            last_traded_quantity=100,
            cumulative_volume=100100
        )
        candles2 = await engine.process_tick(tick2)
        c_1m_updated = [c for c in candles2 if c.timeframe == "1m"][0]
        assert c_1m_updated.open == 1520.0
        assert c_1m_updated.high == 1525.0
        assert c_1m_updated.low == 1520.0
        assert c_1m_updated.close == 1525.0
        assert c_1m_updated.volume == 150  # 50 + 100 delta
        assert c_1m_updated.is_complete is False

    asyncio.run(_test())


def test_volume_calculation_prevents_cumulative_leak(temp_db):
    """
    VOLUME RULE: Never use cumulative daily volume as a single tick's volume.
    Verify delta calculation and prevent volume explosion.
    """
    async def _test():
        engine = CandleEngine()
        base_ts_ms = 1730800800000

        # Initial tick has cumulative volume of 5,000,000 shares
        tick1 = MarketTick(
            symbol="ICICIBANK",
            instrument_key="NSE_EQ|INE090A01021",
            ltp=1250.0,
            exchange_timestamp=base_ts_ms,
            last_traded_quantity=25,
            cumulative_volume=5000000
        )
        candles = await engine.process_tick(tick1)
        c_1m = [c for c in candles if c.timeframe == "1m"][0]
        # Candle volume must NOT be 5,000,000!
        assert c_1m.volume == 25

        # Second tick: cumulative volume moves from 5,000,000 to 5,000,080 (+80 shares)
        tick2 = MarketTick(
            symbol="ICICIBANK",
            instrument_key="NSE_EQ|INE090A01021",
            ltp=1251.0,
            exchange_timestamp=base_ts_ms + 5000,
            last_traded_quantity=80,
            cumulative_volume=5000080
        )
        candles2 = await engine.process_tick(tick2)
        c_1m_2 = [c for c in candles2 if c.timeframe == "1m"][0]
        # Total volume in candle must be 25 + 80 = 105, not millions
        assert c_1m_2.volume == 105

    asyncio.run(_test())


def test_candle_finalization_on_new_interval(temp_db):
    """Verify that previous candle is marked complete when a tick from a new minute arrives."""
    async def _test():
        engine = CandleEngine()
        # 10:00:10
        ts1 = 1730800810000
        tick1 = MarketTick(
            symbol="HDFCBANK",
            instrument_key="NSE_EQ|INE040A01034",
            ltp=1500.0,
            exchange_timestamp=ts1,
            last_traded_quantity=10,
            cumulative_volume=1000
        )
        await engine.process_tick(tick1)

        # 10:01:05 (next minute bucket)
        ts2 = 1730800865000
        tick2 = MarketTick(
            symbol="HDFCBANK",
            instrument_key="NSE_EQ|INE040A01034",
            ltp=1505.0,
            exchange_timestamp=ts2,
            last_traded_quantity=20,
            cumulative_volume=1020
        )
        await engine.process_tick(tick2)

        # Check database: completed candle from 10:00 must be saved with is_complete=1
        db_candles = temp_db.get_candles("HDFCBANK", timeframe="1m", limit=10, include_incomplete=True)
        assert len(db_candles) >= 2
        completed = [c for c in db_candles if c["is_complete"] == 1]
        assert len(completed) >= 1
        assert completed[0]["close"] == 1500.0

    asyncio.run(_test())


def test_duplicate_tick_prevention(temp_db):
    """Verify that sending the identical tick twice does not duplicate candle volume."""
    async def _test():
        engine = CandleEngine()
        ts = 1730800810000
        tick = MarketTick(
            symbol="HDFCBANK",
            instrument_key="NSE_EQ|INE040A01034",
            ltp=1500.0,
            exchange_timestamp=ts,
            last_traded_quantity=50,
            cumulative_volume=1050
        )
        await engine.process_tick(tick)
        # Process identical tick again
        duplicate_result = await engine.process_tick(tick)
        assert duplicate_result == []

    asyncio.run(_test())
