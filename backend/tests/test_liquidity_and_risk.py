"""
Automated unit tests for Liquidity Sweep Detection & Risk Management Engine:
- Swing High & Low liquidity sweeps
- Wick rejection and fakeout risk classification
- Spread and depth imbalance calculation
- Position sizing formula verification:
  Risk Amount = Capital * Risk % / 100
  Position Size = Risk Amount / |Entry - Stop Loss|
- Lot size constraint and R:R ratio validation
"""

import pytest
from app.analysis.liquidity.sweep_detector import analyze_liquidity_and_sweeps
from app.analysis.risk.manager import RiskManager


def test_liquidity_sweep_of_swing_high():
    """
    Verify detection of a swing high sweep:
    Price breaks above previous swing high but closes back below it with a prominent upper wick.
    """
    candles = [
        {"open_time": 100, "open": 100, "high": 105, "low": 99, "close": 102, "volume": 1000},
        {"open_time": 200, "open": 102, "high": 110, "low": 101, "close": 109, "volume": 1200}, # Swing high 110
        {"open_time": 300, "open": 109, "high": 108, "low": 103, "close": 104, "volume": 900},
        {"open_time": 400, "open": 104, "high": 106, "low": 102, "close": 103, "volume": 800},
        # Sweep candle: High reaches 112 (> 110), but closes at 107 (< 110) with upper wick (112 - 107 = 5)
        {"open_time": 500, "open": 104, "high": 112, "low": 103.5, "close": 107, "volume": 2500},
    ]

    res = analyze_liquidity_and_sweeps(candles)
    assert res.sweep_type == "SWING_HIGH_SWEEP"
    assert res.relevant_level == 110.0
    assert res.is_high_risk is True
    assert res.fakeout_risk_level in ("POSSIBLE LIQUIDITY SWEEP", "HIGH FAKEOUT RISK")
    assert "Observed swing high sweep" in res.reason or "Breakout failure" in res.reason


def test_liquidity_sweep_of_swing_low():
    """
    Verify detection of a swing low sweep:
    Price probes below previous swing low but closes back above it with lower wick.
    """
    candles = [
        {"open_time": 100, "open": 100, "high": 102, "low": 95, "close": 96, "volume": 1000}, # Swing low 95
        {"open_time": 200, "open": 96, "high": 101, "low": 96, "close": 100, "volume": 1100},
        {"open_time": 300, "open": 100, "high": 103, "low": 99, "close": 102, "volume": 900},
        # Sweep candle: Low dips to 91 (< 95), but closes back at 97 (> 95) with lower wick (97 - 91 = 6)
        {"open_time": 400, "open": 101, "high": 101.5, "low": 91.0, "close": 97.0, "volume": 2200},
    ]

    res = analyze_liquidity_and_sweeps(candles)
    assert res.sweep_type == "SWING_LOW_SWEEP"
    assert res.relevant_level == 95.0
    assert res.is_high_risk is True
    assert res.fakeout_risk_level in ("POSSIBLE LIQUIDITY SWEEP", "HIGH FAKEOUT RISK")


def test_position_sizing_mathematical_formula():
    """
    Verify position size formula:
    Capital: 100,000 INR
    Risk %: 1.0% -> Risk Amount = 1,000 INR
    Entry: 1500.00 INR
    Stop Loss: 1480.00 INR
    Risk per share: |1500 - 1480| = 20 INR
    Position Size: 1,000 / 20 = 50 shares
    """
    rm = RiskManager(trading_capital=100000.0, risk_percentage=1.0, min_rr_ratio=1.5, lot_size=1)
    
    prof = rm.calculate_trade_risk(
        symbol="HDFCBANK",
        direction="BUY",
        current_price=1500.0,
        structure_stop=1480.10  # Results in 1480.00 stop after buffer
    )

    assert prof.entry_price == 1500.0
    assert prof.stop_loss == 1480.0
    assert prof.risk_amount == 1000.0
    assert prof.suggested_shares == 50
    assert prof.monetary_risk_actual == 1000.0
    assert prof.risk_reward_ratio >= 1.5
    assert prof.is_valid_rr is True


def test_position_sizing_respects_capital_limits():
    """Verify that position size never exceeds total trading capital."""
    # Small account of 5,000 INR on 1500 INR stock
    rm = RiskManager(trading_capital=5000.0, risk_percentage=10.0, min_rr_ratio=1.5)
    prof = rm.calculate_trade_risk(
        symbol="HDFCBANK",
        direction="BUY",
        current_price=1500.0,
        structure_stop=1498.0  # Tight stop 2 INR -> 500 / 2 = 250 shares, but capital only affords 3 shares!
    )
    # Must be capped at floor(5000 / 1500) = 3 shares
    assert prof.suggested_shares == 3
    assert (prof.suggested_shares * prof.entry_price) <= 5000.0

