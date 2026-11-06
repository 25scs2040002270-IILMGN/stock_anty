import time
import pytest
from app.database.models import InstrumentRecord, CandleRecord
from app.market_data.normalization.tick import MarketTick


def test_sqlite_instrument_crud(temp_db):
    """Verify persisting and reading instrument records."""
    rec = InstrumentRecord(
        instrument_key="NSE_EQ|INE040A01034",
        trading_symbol="HDFCBANK",
        exchange="NSE_EQ",
        segment="NSE_EQ",
        instrument_type="EQ",
        tick_size=0.05,
        lot_size=1,
        is_active=True
    )
    temp_db.save_instrument(rec)

    item = temp_db.get_instrument_by_symbol("HDFCBANK")
    assert item is not None
    assert item["instrument_key"] == "NSE_EQ|INE040A01034"
    assert item["trading_symbol"] == "HDFCBANK"
    assert item["is_active"] == 1


def test_sqlite_candle_uniqueness(temp_db):
    """Verify that multiple updates to the same candle bucket update the record without duplicates."""
    c1 = CandleRecord(
        instrument_key="NSE_EQ|INE040A01034",
        symbol="HDFCBANK",
        timeframe="1m",
        open_time=1730800000,
        close_time=1730800060,
        open_datetime_ist="2026-11-05 10:00:00 IST",
        open=1500.0,
        high=1500.0,
        low=1500.0,
        close=1500.0,
        volume=100,
        is_complete=False
    )
    temp_db.save_or_update_candle(c1)

    # Update with new high and volume
    c1.high = 1510.0
    c1.close = 1508.0
    c1.volume = 250
    temp_db.save_or_update_candle(c1)

    rows = temp_db.get_candles("HDFCBANK", timeframe="1m")
    assert len(rows) == 1
    assert rows[0]["high"] == 1510.0
    assert rows[0]["volume"] == 250


def test_sqlite_connection_logs(temp_db):
    """Verify writing and reading connection event logs."""
    temp_db.log_connection_event("UPSTOX", "LIVE", "Market feed connected and streaming ticks", {"latency_ms": 12})
    logs = temp_db.get_connection_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["state"] == "LIVE"
    assert logs[0]["provider"] == "UPSTOX"
    assert logs[0]["details"]["latency_ms"] == 12

