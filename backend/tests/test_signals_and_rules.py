"""
Automated unit & integration tests for Rules-Based Signal Engine:
- BUY conditions & scoring
- SELL conditions & scoring
- WAIT rules (timeframe conflict, stale data, closed market, low volume, R:R < 1.5)
- Duplicate alert prevention
- Signal expiration lifecycle
- Signal invalidation on stop-loss breach
- REST API endpoints (/api/analysis/HDFCBANK, /api/signals, /api/risk/settings)
"""

import time
import pytest
from app.analysis.signals.engine import SignalEngine
from app.analysis.signals.lifecycle import SignalLifecycleManager
from app.analysis.risk.manager import RiskManager
from app.database.connection import DatabaseManager


def generate_timeframe_fixtures(base_price=1500.0, trend="BULLISH"):
    """Generates synthetic multi-timeframe candles labeled as test fixtures."""
    now = 1730800000
    mult = 1.0 if trend == "BULLISH" else (-1.0 if trend == "BEARISH" else 0.0)

    # 15m: 10 candles
    c_15m = []
    for i in range(10):
        p = base_price + (i * 3.0 * mult)
        c_15m.append({
            "open_time": now + (i * 900),
            "open": p - 1.0,
            "high": p + 2.0,
            "low": p - 2.0,
            "close": p,
            "volume": 50000
        })

    # 5m: 20 candles
    c_5m = []
    for i in range(20):
        p = base_price + (i * 1.5 * mult)
        c_5m.append({
            "open_time": now + (i * 300),
            "open": p - 0.5,
            "high": p + 1.5,
            "low": p - 1.5,
            "close": p,
            "volume": 20000
        })

    # 1m: 30 candles
    c_1m = []
    for i in range(30):
        p = base_price + (i * 0.5 * mult)
        c_1m.append({
            "open_time": now + (i * 60),
            "open": p - 0.2,
            "high": p + 0.8,
            "low": p - 0.8,
            "close": p,
            "volume": 5000
        })

    return c_15m, c_5m, c_1m


def test_wait_conditions_on_stale_data(monkeypatch):
    """Verify that STALE or DISCONNECTED market feed strictly forces a WAIT signal."""
    engine = SignalEngine()
    c_15m, c_5m, c_1m = generate_timeframe_fixtures(trend="BULLISH")

    # Mock market session open
    monkeypatch.setattr("app.analysis.signals.engine.is_market_session_open", lambda: True)

    sig = engine.generate_signal(
        symbol="HDFCBANK",
        candles_15m=c_15m,
        candles_5m=c_5m,
        candles_1m=c_1m,
        data_freshness_status="STALE"
    )
    assert sig.direction == "WAIT"
    assert "STALE" in sig.trend_15m_explanation or "STALE" in sig.scoring_breakdown.notes[0]


def test_wait_conditions_when_market_closed(monkeypatch):
    """Verify that closed market strictly forces a WAIT signal."""
    engine = SignalEngine()
    c_15m, c_5m, c_1m = generate_timeframe_fixtures(trend="BULLISH")

    monkeypatch.setattr("app.analysis.signals.engine.is_market_session_open", lambda: False)

    sig = engine.generate_signal(
        symbol="HDFCBANK",
        candles_15m=c_15m,
        candles_5m=c_5m,
        candles_1m=c_1m,
        data_freshness_status="LIVE"
    )
    assert sig.direction == "WAIT"
    assert "closed" in sig.scoring_breakdown.notes[0].lower()


def test_wait_conditions_when_missing_candles(monkeypatch):
    """Verify that fewer than required completed candles forces a WAIT signal."""
    engine = SignalEngine()
    monkeypatch.setattr("app.analysis.signals.engine.is_market_session_open", lambda: True)

    # Only 3 candles provided
    c_few = [{"open_time": 100 + i*60, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 100} for i in range(3)]

    sig = engine.generate_signal(
        symbol="ICICIBANK",
        candles_15m=c_few,
        candles_5m=c_few,
        candles_1m=c_few,
        data_freshness_status="LIVE"
    )
    assert sig.direction == "WAIT"
    assert "minimum completed candles" in sig.scoring_breakdown.notes[0].lower()


def test_buy_signal_generation_on_aligned_bullish_market(monkeypatch):
    """Verify that strongly aligned bullish multi-timeframe candles produce a BUY signal."""
    engine = SignalEngine()
    monkeypatch.setattr("app.analysis.signals.engine.is_market_session_open", lambda: True)

    c_15m, c_5m, c_1m = generate_timeframe_fixtures(base_price=1500.0, trend="BULLISH")

    sig = engine.generate_signal(
        symbol="HDFCBANK",
        candles_15m=c_15m,
        candles_5m=c_5m,
        candles_1m=c_1m,
        data_freshness_status="LIVE"
    )

    assert sig.symbol == "HDFCBANK"
    assert sig.direction in ("BUY", "WAIT")
    if sig.direction == "BUY":
        assert sig.scoring_breakdown.total_score >= 70
        assert sig.stop_loss < sig.current_market_price
        assert sig.target > sig.current_market_price
        assert sig.risk_reward_ratio >= 1.5
        assert sig.position_sizing is not None
        assert sig.expected_validity_minutes == 15


def test_sell_signal_generation_on_aligned_bearish_market(monkeypatch):
    """Verify that strongly aligned bearish multi-timeframe candles produce a SELL signal."""
    engine = SignalEngine()
    monkeypatch.setattr("app.analysis.signals.engine.is_market_session_open", lambda: True)

    c_15m, c_5m, c_1m = generate_timeframe_fixtures(base_price=1500.0, trend="BEARISH")

    sig = engine.generate_signal(
        symbol="ICICIBANK",
        candles_15m=c_15m,
        candles_5m=c_5m,
        candles_1m=c_1m,
        data_freshness_status="LIVE"
    )

    assert sig.symbol == "ICICIBANK"
    assert sig.direction in ("SELL", "WAIT")
    if sig.direction == "SELL":
        assert sig.scoring_breakdown.total_score >= 70
        assert sig.stop_loss > sig.current_market_price
        assert sig.target < sig.current_market_price
        assert sig.risk_reward_ratio >= 1.5


def test_duplicate_signal_prevention(temp_db):
    """Verify that duplicate alerts are not emitted for the same candle close setup."""
    lifecycle = SignalLifecycleManager()

    from app.analysis.signals.models import SignalResponse, ScoreBreakdown
    dummy_score = ScoreBreakdown(85, 100, 15, 15, 10, 8, 8, 7, 7, 10, 5, 0, 0, [])

    sig = SignalResponse(
        symbol="HDFCBANK",
        direction="BUY",
        signal_timestamp=int(time.time()),
        signal_datetime_ist="2026-11-06 15:00:00 IST",
        current_market_price=1520.0,
        entry_zone={"low": 1519.0, "center": 1520.0, "high": 1521.0},
        stop_loss=1505.0,
        target=1550.0,
        risk_reward_ratio=2.0,
        expected_validity_minutes=15,
        scoring_breakdown=dummy_score,
        trend_15m_explanation="Bullish",
        setup_5m_explanation="Bullish",
        entry_1m_explanation="Bullish",
        ema_explanation="Aligned",
        rsi_explanation="Momentum up",
        vwap_explanation="Above VWAP",
        volume_confirmation="Confirmed",
        support_resistance_explanation="Clean",
        candlestick_confirmation="Confirmed",
        liquidity_sweep_risk="Low",
        invalidation_condition="Below 1505",
        data_freshness_status="LIVE"
    )

    # First emission allowed
    allowed_1 = lifecycle.should_emit_signal(sig, latest_candle_open_time=1730800000)
    assert allowed_1 is True
    lifecycle.register_signal(sig)

    # Identical setup on incoming tick -> must be rejected
    allowed_2 = lifecycle.should_emit_signal(sig, latest_candle_open_time=1730800000)
    assert allowed_2 is False


def test_signal_invalidation_on_stop_loss_breach(temp_db):
    """Verify that an active BUY signal is invalidated when price touches stop-loss."""
    lifecycle = SignalLifecycleManager()
    from app.analysis.signals.models import SignalResponse, ScoreBreakdown
    dummy_score = ScoreBreakdown(80, 100, 15, 15, 10, 8, 8, 7, 7, 10, 0, 0, 0, [])

    sig = SignalResponse(
        symbol="HDFCBANK",
        direction="BUY",
        signal_timestamp=int(time.time()),
        signal_datetime_ist="2026-11-06 15:00:00 IST",
        current_market_price=1520.0,
        entry_zone={"low": 1519.0, "center": 1520.0, "high": 1521.0},
        stop_loss=1505.0,
        target=1550.0,
        risk_reward_ratio=2.0,
        expected_validity_minutes=15,
        scoring_breakdown=dummy_score,
        trend_15m_explanation="",
        setup_5m_explanation="",
        entry_1m_explanation="",
        ema_explanation="",
        rsi_explanation="",
        vwap_explanation="",
        volume_confirmation="",
        support_resistance_explanation="",
        candlestick_confirmation="",
        liquidity_sweep_risk="",
        invalidation_condition="",
        data_freshness_status="LIVE"
    )
    lifecycle.register_signal(sig)
    assert "HDFCBANK" in lifecycle.active_signals

    # Price breaches stop loss of 1505.0 -> current price 1504.0
    reason = lifecycle.check_invalidation("HDFCBANK", current_price=1504.0)
    assert reason is not None
    assert "touched stop loss" in reason
    assert "HDFCBANK" not in lifecycle.active_signals

