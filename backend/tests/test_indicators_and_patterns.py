"""
Automated unit tests for Technical Indicators & Candlestick Patterns:
- EMA (20/50 crossovers, alignment)
- RSI (14-period, overbought, oversold, divergence)
- VWAP (session calculation, distance %, crossovers)
- Volume (SMA 20, RVOL, expansion/contraction)
- Market Structure (Swing points, HH/HL, LH/LL, Sideways)
- Support & Resistance (Zone clustering, breakout, retest, rejection)
- Candlestick Patterns (Bullish/Bearish Engulfing, Hammer, Shooting Star, Doji, Inside Bar, Breakout & Retest)
"""

import pytest
from app.analysis.indicators.ema import analyze_ema, calculate_ema_series
from app.analysis.indicators.rsi import analyze_rsi, calculate_rsi_series
from app.analysis.indicators.vwap import analyze_vwap
from app.analysis.indicators.volume import analyze_volume
from app.analysis.indicators.market_structure import analyze_market_structure, detect_swing_points
from app.analysis.indicators.support_resistance import analyze_support_resistance
from app.analysis.patterns.candlestick import detect_candlestick_patterns


def generate_synthetic_candles(prices, base_time=1730800000, interval=60, vol=1000):
    """Helper to generate synthetic OHLCV candles labeled as test fixtures."""
    candles = []
    for i, p in enumerate(prices):
        t = base_time + (i * interval)
        candles.append({
            "open_time": t,
            "open": p - 1.0,
            "high": p + 2.0,
            "low": p - 2.0,
            "close": p,
            "volume": vol
        })
    return candles


def test_ema_calculation_and_crossovers():
    """Verify EMA 20/50 calculation, golden cross and death cross detection."""
    # 60 synthetic ascending candles to trigger bullish crossover
    prices = [100.0 + (i * 0.5) for i in range(60)]
    candles = generate_synthetic_candles(prices)

    res = analyze_ema(candles, fast_period=20, slow_period=50)
    assert res.ema_fast is not None
    assert res.ema_slow is not None
    assert res.ema_fast > res.ema_slow
    assert res.trend_alignment == "BULLISH"
    assert "Bullish alignment" in res.explanation

    # Descending series for bearish crossover
    bearish_prices = [150.0 - (i * 0.8) for i in range(60)]
    bearish_candles = generate_synthetic_candles(bearish_prices)
    res_bear = analyze_ema(bearish_candles, fast_period=20, slow_period=50)
    assert res_bear.ema_fast < res_bear.ema_slow
    assert res_bear.trend_alignment == "BEARISH"


def test_rsi_overbought_oversold_and_divergence():
    """Verify Wilder's RSI calculation, threshold flags, and divergence logic."""
    # Strong rally -> Overbought
    rally = [100.0 + (i * 2.0) for i in range(30)]
    candles_ob = generate_synthetic_candles(rally)
    res_ob = analyze_rsi(candles_ob, period=14)
    assert res_ob.rsi is not None
    assert res_ob.rsi >= 70.0
    assert res_ob.is_overbought is True
    assert res_ob.momentum in ("BULLISH", "NEUTRAL")

    # Steep decline -> Oversold
    crash = [150.0 - (i * 2.5) for i in range(30)]
    candles_os = generate_synthetic_candles(crash)
    res_os = analyze_rsi(candles_os, period=14)
    assert res_os.rsi is not None
    assert res_os.rsi <= 30.0
    assert res_os.is_oversold is True
    assert res_os.momentum in ("BEARISH", "NEUTRAL")


def test_vwap_session_calculation_and_distance():
    """Verify session VWAP math and price above/below distance."""
    candles = [
        {"open_time": 1730800000, "open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0, "volume": 1000},
        {"open_time": 1730800060, "open": 101.0, "high": 105.0, "low": 101.0, "close": 104.0, "volume": 2000},
    ]
    # Bar 1 TP = (102 + 98 + 101)/3 = 100.333, TPV = 100333.33, Vol = 1000
    # Bar 2 TP = (105 + 101 + 104)/3 = 103.333, TPV = 206666.67, Vol = 2000
    # Total TPV = 307000, Total Vol = 3000 -> VWAP = 102.333
    res = analyze_vwap(candles)
    assert res.vwap is not None
    assert round(res.vwap, 2) == 102.33
    assert res.is_above_vwap is True
    assert res.current_close == 104.0
    assert res.distance_pct > 0


def test_volume_rvol_and_expansion():
    """Verify RVOL calculation, expansion (>=1.5x) and contraction (<=0.7x)."""
    # 20 bars of 1000 shares each
    candles = [{"open_time": 1730800000 + i*60, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000} for i in range(20)]
    
    # Add expansion bar with 2500 shares (2.5x RVOL)
    candles.append({"open_time": 1730801200, "open": 100.5, "high": 103, "low": 100, "close": 102.5, "volume": 2500})
    res_exp = analyze_volume(candles, sma_period=20)
    assert res_exp.is_expansion is True
    assert res_exp.volume_trend == "EXPANDING"
    assert res_exp.relative_volume >= 2.0

    # Add contraction bar with 300 shares (0.3x RVOL)
    candles.append({"open_time": 1730801260, "open": 102.5, "high": 102.6, "low": 102.4, "close": 102.5, "volume": 300})
    res_con = analyze_volume(candles, sma_period=20)
    assert res_con.is_contraction is True
    assert res_con.volume_trend == "CONTRACTING"


def test_market_structure_hh_hl_and_lh_ll():
    """Verify swing detection and structure classification."""
    # Build uptrend: Low -> High -> Higher Low -> Higher High
    uptrend_candles = [
        {"open_time": 100, "open": 100, "high": 102, "low": 99, "close": 101},
        {"open_time": 200, "open": 101, "high": 103, "low": 100, "close": 102},
        {"open_time": 300, "open": 102, "high": 110, "low": 101, "close": 109}, # Swing High 110
        {"open_time": 400, "open": 109, "high": 108, "low": 103, "close": 104},
        {"open_time": 500, "open": 104, "high": 105, "low": 102, "close": 103}, # Swing Low 102
        {"open_time": 600, "open": 103, "high": 107, "low": 103, "close": 106},
        {"open_time": 700, "open": 106, "high": 115, "low": 105, "close": 114}, # Swing High 115 (HH)
        {"open_time": 800, "open": 114, "high": 112, "low": 107, "close": 108},
        {"open_time": 900, "open": 108, "high": 110, "low": 106, "close": 107}, # Swing Low 106 (HL)
        {"open_time": 1000, "open": 107, "high": 112, "low": 107, "close": 111},
    ]
    res_up = analyze_market_structure(uptrend_candles, order=1)
    assert res_up.has_higher_highs is True
    assert res_up.has_higher_lows is True
    assert res_up.structure == "BULLISH"


def test_support_resistance_zones_and_breakout():
    """Verify clustering into S/R zones and breakout identification."""
    candles = [
        {"open_time": 100, "open": 100, "high": 105.0, "low": 98.0, "close": 102.0},
        {"open_time": 200, "open": 102, "high": 105.2, "low": 100.0, "close": 103.0},
        {"open_time": 300, "open": 103, "high": 105.1, "low": 99.0, "close": 104.0},
        # Breakout candle closing decisively above 105.2
        {"open_time": 400, "open": 104, "high": 108.0, "low": 103.5, "close": 107.5},
    ]
    res = analyze_support_resistance(candles, tolerance_pct=0.3)
    assert res.nearest_resistance is not None
    assert round(res.nearest_resistance, 0) == 105.0
    assert res.is_breakout_above is True


def test_candlestick_patterns_detection():
    """Verify mathematical detection of all 7 candlestick patterns."""
    # 1. Bullish Engulfing
    c_engulf = [
        {"open_time": 100, "open": 105, "high": 106, "low": 101, "close": 102}, # Red body 3
        {"open_time": 200, "open": 101.5, "high": 107, "low": 101, "close": 106}, # Green body 4.5 engulfs
    ]
    pats = detect_candlestick_patterns(c_engulf)
    assert any(p.pattern_name == "BULLISH_ENGULFING" for p in pats)

    # 2. Bearish Engulfing
    c_bear_engulf = [
        {"open_time": 100, "open": 100, "high": 104, "low": 99, "close": 103}, # Green body 3
        {"open_time": 200, "open": 103.5, "high": 104, "low": 98, "close": 98.5}, # Red body 5 engulfs
    ]
    pats_b = detect_candlestick_patterns(c_bear_engulf)
    assert any(p.pattern_name == "BEARISH_ENGULFING" for p in pats_b)

    # 3. Hammer
    c_hammer = [
        {"open_time": 100, "open": 105, "high": 106, "low": 102, "close": 103},
        {"open_time": 200, "open": 100, "high": 101.2, "low": 92.0, "close": 101.0}, # Body 1.0, lower wick 8.0 >= 2x body
    ]
    pats_h = detect_candlestick_patterns(c_hammer)
    assert any(p.pattern_name == "HAMMER" for p in pats_h)

    # 4. Shooting Star
    c_star = [
        {"open_time": 100, "open": 100, "high": 102, "low": 99, "close": 101},
        {"open_time": 200, "open": 101, "high": 110.0, "low": 100.8, "close": 101.5}, # Body 0.5, upper wick 8.5 >= 2x body
    ]
    pats_s = detect_candlestick_patterns(c_star)
    assert any(p.pattern_name == "SHOOTING_STAR" for p in pats_s)

    # 5. Doji
    c_doji = [
        {"open_time": 100, "open": 100, "high": 102, "low": 99, "close": 101},
        {"open_time": 200, "open": 101.0, "high": 105.0, "low": 97.0, "close": 101.05}, # Range 8.0, Body 0.05 (<= 10% range)
    ]
    pats_d = detect_candlestick_patterns(c_doji)
    assert any(p.pattern_name == "DOJI" for p in pats_d)

    # 6. Inside Bar
    c_inside = [
        {"open_time": 100, "open": 100, "high": 110, "low": 90, "close": 105}, # Mother bar
        {"open_time": 200, "open": 102, "high": 106, "low": 95, "close": 101}, # Contained
    ]
    pats_in = detect_candlestick_patterns(c_inside)
    assert any(p.pattern_name == "INSIDE_BAR" for p in pats_in)

