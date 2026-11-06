from typing import Dict, Any, List, Tuple
from app.analysis.signals.models import ScoreBreakdown


def calculate_signal_score(
    target_direction: str,  # 'BUY' or 'SELL'
    trend_15m: str,         # 'BULLISH', 'BEARISH', 'SIDEWAYS'
    setup_5m: str,          # 'BULLISH', 'BEARISH', 'SIDEWAYS'
    entry_1m: str,          # 'BULLISH', 'BEARISH', 'NEUTRAL'
    ema_align: str,         # 'BULLISH', 'BEARISH', 'NEUTRAL'
    has_ema_cross: bool,
    vwap_align: str,        # 'BULLISH', 'BEARISH'
    has_vwap_cross: bool,
    rsi_momentum: str,      # 'BULLISH', 'BEARISH', 'NEUTRAL'
    has_rsi_divergence: bool,
    is_rsi_extreme: bool,   # Overbought for BUY or Oversold for SELL
    volume_confirmed: bool,
    is_volume_expansion: bool,
    structure: str,         # 'BULLISH', 'BEARISH', 'SIDEWAYS'
    is_at_key_level: bool,  # Support for BUY or Resistance for SELL
    has_candlestick_pat: bool,
    candlestick_dir: str,   # 'BULLISH', 'BEARISH', 'NEUTRAL'
    fakeout_risk_level: str # 'LOW FAKEOUT RISK', 'MODERATE FAKEOUT RISK', 'HIGH FAKEOUT RISK', 'POSSIBLE LIQUIDITY SWEEP'
) -> ScoreBreakdown:
    """
    Transparent scoring system evaluating analytical alignment for a candidate trade direction.
    IMPORTANT: The score is NOT a win probability. A score of 80/100 reflects technical condition alignment,
    not an 80% likelihood of profit.
    """
    is_buy = target_direction == "BUY"

    trend_score = 0
    setup_score = 0
    entry_score = 0
    ema_score = 0
    vwap_score = 0
    rsi_score = 0
    vol_score = 0
    struct_score = 0
    sr_score = 0
    candle_score = 0
    liquidity_penalty = 0
    notes: List[str] = []

    # 1. 15-Minute Macro Trend (Max: 15 pts)
    match_trend = "BULLISH" if is_buy else "BEARISH"
    opposite_trend = "BEARISH" if is_buy else "BULLISH"
    if trend_15m == match_trend:
        trend_score = 15
        notes.append(f"15m macro trend confirms {match_trend} (+15 pts)")
    elif trend_15m == "SIDEWAYS":
        trend_score = 5
        notes.append("15m macro trend is neutral/sideways (+5 pts)")
    else:
        trend_score = 0
        notes.append(f"15m macro trend opposes trade ({opposite_trend}) (0 pts)")

    # 2. 5-Minute Setup Confirmation (Max: 15 pts)
    if setup_5m == match_trend:
        setup_score = 15
        notes.append(f"5m setup confirms {match_trend} (+15 pts)")
    elif setup_5m == "SIDEWAYS":
        setup_score = 5
        notes.append("5m setup is consolidating (+5 pts)")
    else:
        setup_score = 0
        notes.append(f"5m setup conflicts with direction (0 pts)")

    # 3. 1-Minute Entry Timing (Max: 10 pts)
    if entry_1m == match_trend:
        entry_score = 10
        notes.append(f"1m timing aligned with {match_trend} (+10 pts)")
    elif entry_1m == "NEUTRAL":
        entry_score = 4
        notes.append("1m timing is neutral (+4 pts)")
    else:
        entry_score = 0
        notes.append("1m timing counter to direction (0 pts)")

    # 4. EMA Alignment (Max: 10 pts)
    if ema_align == match_trend:
        ema_score = 8
        if has_ema_cross:
            ema_score += 2
            notes.append(f"EMA 20/50 alignment + fresh crossover (+10 pts)")
        else:
            notes.append(f"EMA 20/50 alignment (+8 pts)")
    elif ema_align == "NEUTRAL":
        ema_score = 3
        notes.append("EMA alignment neutral (+3 pts)")
    else:
        ema_score = 0
        notes.append("EMA alignment opposed (0 pts)")

    # 5. VWAP Alignment (Max: 10 pts)
    if vwap_align == match_trend:
        vwap_score = 8
        if has_vwap_cross:
            vwap_score += 2
            notes.append(f"Price on favorable side of session VWAP + crossover (+10 pts)")
        else:
            notes.append(f"Price on favorable side of session VWAP (+8 pts)")
    else:
        vwap_score = 0
        notes.append("Price on unfavorable side of session VWAP (0 pts)")

    # 6. RSI Momentum & Divergence (Max: 10 pts)
    if is_rsi_extreme:
        rsi_score = 0
        notes.append("RSI at extreme exhaustion zone (0 pts)")
    elif rsi_momentum == match_trend:
        rsi_score = 7
        if has_rsi_divergence:
            rsi_score += 3
            notes.append(f"RSI momentum supportive + divergence confirmation (+10 pts)")
        else:
            notes.append(f"RSI momentum supportive (+7 pts)")
    elif rsi_momentum == "NEUTRAL":
        rsi_score = 4
        notes.append("RSI momentum neutral (+4 pts)")
    else:
        rsi_score = 0
        notes.append("RSI momentum unsupportive (0 pts)")

    # 7. Volume Dynamics (Max: 10 pts)
    if volume_confirmed:
        vol_score = 7
        if is_volume_expansion:
            vol_score += 3
            notes.append("Volume expansion confirming price action (+10 pts)")
        else:
            notes.append("Volume above average (+7 pts)")
    else:
        vol_score = 2
        notes.append("Volume below average / low participation (+2 pts)")

    # 8. Market Structure (Max: 10 pts)
    if structure == match_trend:
        struct_score = 10
        notes.append(f"Market structure strictly {match_trend} (+10 pts)")
    elif structure == "SIDEWAYS":
        struct_score = 4
        notes.append("Market structure sideways / range-bound (+4 pts)")
    else:
        struct_score = 0
        notes.append("Market structure counter-trend (0 pts)")

    # 9. Support & Resistance Placement (Max: 5 pts)
    if is_at_key_level:
        sr_score = 5
        notes.append("Price reacting at high-probability S/R zone (+5 pts)")
    else:
        sr_score = 2
        notes.append("Price in mid-range between major S/R zones (+2 pts)")

    # 10. Candlestick Confirmation (Max: 5 pts)
    if has_candlestick_pat and candlestick_dir == match_trend:
        candle_score = 5
        notes.append("Candlestick pattern reinforces setup (+5 pts)")
    elif has_candlestick_pat and candlestick_dir == opposite_trend:
        candle_score = 0
        notes.append("Candlestick pattern counter to setup (0 pts)")
    else:
        candle_score = 2
        notes.append("No definitive single-candlestick trigger (+2 pts)")

    # 11. Liquidity Sweep & Fakeout Penalty (Deduction)
    if fakeout_risk_level == "POSSIBLE LIQUIDITY SWEEP":
        liquidity_penalty = 35
        notes.append("PENALTY: Possible liquidity sweep / trap detected (-35 pts)")
    elif fakeout_risk_level == "HIGH FAKEOUT RISK":
        liquidity_penalty = 25
        notes.append("PENALTY: High fakeout risk / rejected wick (-25 pts)")
    elif fakeout_risk_level == "MODERATE FAKEOUT RISK":
        liquidity_penalty = 10
        notes.append("PENALTY: Moderate fakeout risk / low participation (-10 pts)")

    raw_sum = (
        trend_score + setup_score + entry_score + ema_score + vwap_score +
        rsi_score + vol_score + struct_score + sr_score + candle_score
    )
    total_score = max(0, min(100, raw_sum - liquidity_penalty))

    return ScoreBreakdown(
        total_score=total_score,
        max_score=100,
        trend_15m_score=trend_score,
        setup_5m_score=setup_score,
        entry_1m_score=entry_score,
        ema_score=ema_score,
        vwap_score=vwap_score,
        rsi_score=rsi_score,
        volume_score=vol_score,
        structure_score=struct_score,
        sr_score=sr_score,
        candlestick_score=candle_score,
        liquidity_penalty=liquidity_penalty,
        notes=notes
    )

