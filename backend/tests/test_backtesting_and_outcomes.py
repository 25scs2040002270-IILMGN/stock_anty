"""Unit and Integration Tests for Step 3:
- Backtesting Engine
- Zero look-ahead bias validation
- Conservative same-bar SL/Target resolution
- NSE equity brokerage and statutory charges
- Train / Validation / Test walk-forward splits
- Signal outcome evaluation
- Daily risk summary and evaluated history APIs
"""

import pytest
import asyncio
import pandas as pd
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.backtesting.data_loader import (
    validate_and_parse_csv,
    resample_candles,
    generate_synthetic_candles,
    ALLOWED_SYMBOLS
)
from app.backtesting.engine import BacktestEngine
from app.analysis.signals.outcome_evaluator import (
    calculate_nse_charges,
    evaluate_signal_outcome
)
from app.database.models import SignalRecord
from app.database.connection import get_db

client = TestClient(app)


def test_allowed_symbols_strict():
    """Verify strictly only HDFCBANK and ICICIBANK are permitted."""
    assert "HDFCBANK" in ALLOWED_SYMBOLS
    assert "ICICIBANK" in ALLOWED_SYMBOLS
    assert "RELIANCE" not in ALLOWED_SYMBOLS
    assert len(ALLOWED_SYMBOLS) == 2


def test_csv_validation_valid():
    """Test CSV validation parses compliant 1-minute OHLCV data."""
    csv_data = """timestamp,open,high,low,close,volume
2026-11-02 09:15:00,1600.0,1605.0,1598.0,1603.5,15000
2026-11-02 09:16:00,1603.5,1607.0,1602.0,1606.0,18000
2026-11-02 09:17:00,1606.0,1608.5,1604.0,1605.0,12000
"""
    df = validate_and_parse_csv(csv_data, "HDFCBANK")
    assert len(df) == 3
    assert df.iloc[0]["close"] == 1603.5
    assert df.iloc[1]["volume"] == 18000


def test_csv_validation_rejects_unauthorized_symbol():
    """Test CSV loader rejects any ticker other than HDFCBANK or ICICIBANK."""
    csv_data = "timestamp,open,high,low,close,volume\n2026-11-02 09:15:00,2500,2510,2490,2505,10000"
    with pytest.raises(ValueError, match="not allowed"):
        validate_and_parse_csv(csv_data, "RELIANCE")


def test_csv_validation_rejects_invalid_ohlc():
    """Test CSV loader catches bad data where High < Low."""
    csv_data = """timestamp,open,high,low,close,volume
2026-11-02 09:15:00,1600.0,1590.0,1610.0,1603.5,15000
"""
    with pytest.raises(ValueError, match="High/Low/Open/Close logical inconsistency"):
        validate_and_parse_csv(csv_data, "HDFCBANK")


def test_resample_candles_to_5m():
    """Test resampling 1m candles into 5m OHLCV aggregates."""
    synthetic = generate_synthetic_candles("HDFCBANK", n_bars=60)
    df_1m = synthetic["1m"]
    df_5m = resample_candles(df_1m, 5)
    assert len(df_5m) == 12
    # Verify high of 5m is max of constituent 1m
    first_5m_high = df_5m.iloc[0]["high"]
    constituent_1m_high = df_1m.iloc[0:5]["high"].max()
    assert first_5m_high == constituent_1m_high


def test_nse_equity_charges_calculation():
    """Test realistic Indian NSE intraday equity charges calculation."""
    buy_turnover = 100000.0  # ₹1 Lakh buy
    sell_turnover = 101000.0  # ₹1.01 Lakh sell
    charges = calculate_nse_charges(buy_turnover, sell_turnover)
    
    assert charges["brokerage"] > 0
    assert charges["stt"] > 0
    assert charges["exchange_charges"] > 0
    assert charges["gst"] > 0
    assert charges["stamp_duty"] > 0
    assert charges["total_charges"] > 0
    # On 1 Lakh turnover, total charges are typically ₹50-₹80
    assert 30.0 < charges["total_charges"] < 150.0


def test_outcome_evaluator_hit_target():
    """Test signal evaluator successfully resolves target hit."""
    sig = SignalRecord(
        symbol="HDFCBANK",
        direction="BUY",
        signal_timestamp=1700000000,
        signal_datetime_ist="2026-11-02 09:15:00",
        current_market_price=1600.0,
        entry_price=1600.0,
        entry_zone_low=1599.0,
        entry_zone_high=1601.0,
        stop_loss=1590.0,
        target=1620.0,
        risk_reward_ratio=2.0,
        score=85,
        status="ACTIVE"
    )
    subsequent = [
        {"timestamp": "2026-11-02 09:16:00", "open": 1601.0, "high": 1608.0, "low": 1599.0, "close": 1605.0},
        {"timestamp": "2026-11-02 09:17:00", "open": 1605.0, "high": 1622.0, "low": 1603.0, "close": 1621.0}
    ]
    res = evaluate_signal_outcome(sig, subsequent)
    assert res["outcome"] == "HIT_TARGET"
    assert res["gross_pnl"] > 0
    assert res["net_pnl"] > 0
    assert res["duration_minutes"] == 2


def test_outcome_evaluator_conservative_resolution():
    """Test that if BOTH stop loss and target are crossed in same candle, SL is chosen."""
    sig = SignalRecord(
        symbol="ICICIBANK",
        direction="BUY",
        signal_timestamp=1700000000,
        signal_datetime_ist="2026-11-02 09:15:00",
        current_market_price=1100.0,
        entry_price=1100.0,
        entry_zone_low=1099.0,
        entry_zone_high=1101.0,
        stop_loss=1090.0,
        target=1120.0,
        risk_reward_ratio=2.0,
        score=80,
        status="ACTIVE"
    )
    # Violent candle that spikes to 1125 but also plunges to 1085
    subsequent = [
        {"timestamp": "2026-11-02 09:16:00", "open": 1100.0, "high": 1125.0, "low": 1085.0, "close": 1110.0}
    ]
    res = evaluate_signal_outcome(sig, subsequent)
    assert res["outcome"] == "HIT_STOP_LOSS"
    assert res["net_pnl"] < 0
    assert "conservative SL exit" in res["reason"]


def test_outcome_evaluator_expiration():
    """Test signal expires when max duration passes without hitting SL or target."""
    sig = SignalRecord(
        symbol="HDFCBANK",
        direction="BUY",
        signal_timestamp=1700000000,
        signal_datetime_ist="2026-11-02 09:15:00",
        current_market_price=1600.0,
        entry_price=1600.0,
        entry_zone_low=1599.0,
        entry_zone_high=1601.0,
        stop_loss=1580.0,
        target=1640.0,
        risk_reward_ratio=2.0,
        score=80,
        status="ACTIVE"
    )
    # 15 flat candles
    subsequent = [
        {"timestamp": f"2026-11-02 09:{16+i:02d}:00", "open": 1600.0, "high": 1602.0, "low": 1598.0, "close": 1601.0}
        for i in range(15)
    ]
    res = evaluate_signal_outcome(sig, subsequent, max_horizon_minutes=15)
    assert res["outcome"] == "EXPIRED"
    assert res["duration_minutes"] == 15


def test_backtest_engine_walk_forward_execution():
    """Test full chronological walk-forward backtest on synthetic multi-timeframe candles."""
    candles = generate_synthetic_candles("HDFCBANK", n_bars=150, regime="bullish")
    engine = BacktestEngine(
        symbol="HDFCBANK",
        initial_capital=100000.0,
        risk_per_trade_pct=0.01,
        slippage_pct=0.0005,
        min_rr_ratio=1.5
    )
    report = engine.run(df_1m=candles["1m"], df_5m=candles["5m"], df_15m=candles["15m"])
    
    assert report["symbol"] == "HDFCBANK"
    assert report["total_signals"] > 0
    assert "splits" in report
    assert "train" in report["splits"]
    assert "validation" in report["splits"]
    assert "test" in report["splits"]
    assert "regimes" in report
    assert "equity_curve" in report
    assert isinstance(report["trades"], list)


def test_api_run_backtest_endpoint():
    """Test POST /api/backtest/run endpoint."""
    payload = {
        "symbol": "HDFCBANK",
        "initial_capital": 100000.0,
        "risk_per_trade_pct": 0.01,
        "slippage_pct": 0.0005,
        "min_rr_ratio": 1.5,
        "source": "synthetic",
        "synthetic_bars": 120,
        "synthetic_regime": "bullish"
    }
    response = client.post("/api/backtest/run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["symbol"] == "HDFCBANK"
    assert "win_rate" in data
    assert "trades" in data
    assert "id" in data


def test_api_daily_summary_and_evaluated_history():
    """Test GET /api/signals/daily-summary and GET /api/signals/evaluated-history."""
    resp1 = client.get("/api/signals/daily-summary")
    assert resp1.status_code == 200
    summary = resp1.json()["data"]
    assert "trading_capital" in summary
    assert "risk_percentage" in summary

    resp2 = client.get("/api/signals/evaluated-history?symbol=HDFCBANK&limit=10")
    assert resp2.status_code == 200
    history = resp2.json()["data"]
    assert isinstance(history, list)
