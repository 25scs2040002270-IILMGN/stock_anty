from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np


@dataclass
class EMAResult:
    ema_fast: Optional[float]           # EMA 20
    ema_slow: Optional[float]           # EMA 50
    prev_ema_fast: Optional[float]      # Previous candle EMA 20
    prev_ema_slow: Optional[float]      # Previous candle EMA 50
    current_close: float
    is_bullish_cross: bool              # EMA 20 crossed above EMA 50 on confirmed close
    is_bearish_cross: bool              # EMA 20 crossed below EMA 50 on confirmed close
    trend_alignment: str                # 'BULLISH', 'BEARISH', 'NEUTRAL'
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ema_20": round(self.ema_fast, 2) if self.ema_fast is not None else None,
            "ema_50": round(self.ema_slow, 2) if self.ema_slow is not None else None,
            "is_bullish_cross": self.is_bullish_cross,
            "is_bearish_cross": self.is_bearish_cross,
            "trend_alignment": self.trend_alignment,
            "explanation": self.explanation
        }


def calculate_ema_series(close_series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average using standard ewm."""
    if len(close_series) == 0:
        return pd.Series(dtype=float)
    return close_series.ewm(span=period, adjust=False).mean()


def analyze_ema(candles: List[Dict[str, Any]], fast_period: int = 20, slow_period: int = 50) -> EMAResult:
    """
    Analyzes EMA 20 and EMA 50 on completed candles.
    Calculates crossovers and trend alignment.
    """
    if not candles:
        return EMAResult(
            ema_fast=None,
            ema_slow=None,
            prev_ema_fast=None,
            prev_ema_slow=None,
            current_close=0.0,
            is_bullish_cross=False,
            is_bearish_cross=False,
            trend_alignment="NEUTRAL",
            explanation="Insufficient candle data for EMA calculation."
        )

    df = pd.DataFrame(candles)
    if "close" not in df.columns or len(df) < 2:
        curr_c = float(df["close"].iloc[-1]) if "close" in df.columns and len(df) > 0 else 0.0
        return EMAResult(
            ema_fast=None,
            ema_slow=None,
            prev_ema_fast=None,
            prev_ema_slow=None,
            current_close=curr_c,
            is_bullish_cross=False,
            is_bearish_cross=False,
            trend_alignment="NEUTRAL",
            explanation="Need at least 2 completed candles to evaluate EMA."
        )

    close_series = df["close"].astype(float)
    ema_fast_s = calculate_ema_series(close_series, fast_period)
    ema_slow_s = calculate_ema_series(close_series, slow_period)

    curr_close = float(close_series.iloc[-1])
    curr_fast = float(ema_fast_s.iloc[-1])
    curr_slow = float(ema_slow_s.iloc[-1])

    prev_fast = float(ema_fast_s.iloc[-2])
    prev_slow = float(ema_slow_s.iloc[-2])

    # Crossover detection on the confirmed candle close
    is_bullish_cross = (prev_fast <= prev_slow) and (curr_fast > curr_slow)
    is_bearish_cross = (prev_fast >= prev_slow) and (curr_fast < curr_slow)

    # Trend alignment logic:
    # BULLISH: Close > EMA 20 and EMA 20 > EMA 50
    # BEARISH: Close < EMA 20 and EMA 20 < EMA 50
    # NEUTRAL: Mixed or compressing
    if len(df) < slow_period:
        # Fewer candles than slow period: provisional alignment
        if curr_close > curr_fast:
            trend_alignment = "BULLISH"
            explanation = f"Price ({curr_close:.2f}) > EMA{fast_period} ({curr_fast:.2f}); EMA{slow_period} initializing ({len(df)} candles)."
        elif curr_close < curr_fast:
            trend_alignment = "BEARISH"
            explanation = f"Price ({curr_close:.2f}) < EMA{fast_period} ({curr_fast:.2f}); EMA{slow_period} initializing."
        else:
            trend_alignment = "NEUTRAL"
            explanation = f"Price ({curr_close:.2f}) hovering at EMA{fast_period}."
    else:
        if curr_close > curr_fast > curr_slow:
            trend_alignment = "BULLISH"
            explanation = f"Bullish alignment: Price ({curr_close:.2f}) > EMA{fast_period} ({curr_fast:.2f}) > EMA{slow_period} ({curr_slow:.2f})."
        elif curr_close < curr_fast < curr_slow:
            trend_alignment = "BEARISH"
            explanation = f"Bearish alignment: Price ({curr_close:.2f}) < EMA{fast_period} ({curr_fast:.2f}) < EMA{slow_period} ({curr_slow:.2f})."
        elif curr_fast > curr_slow and curr_close < curr_fast:
            trend_alignment = "NEUTRAL"
            explanation = f"Pullback in uptrend: Price ({curr_close:.2f}) pulled below EMA{fast_period} ({curr_fast:.2f}) but above EMA{slow_period} ({curr_slow:.2f})."
        elif curr_fast < curr_slow and curr_close > curr_fast:
            trend_alignment = "NEUTRAL"
            explanation = f"Rebound in downtrend: Price ({curr_close:.2f}) above EMA{fast_period} ({curr_fast:.2f}) but below EMA{slow_period} ({curr_slow:.2f})."
        else:
            trend_alignment = "NEUTRAL"
            explanation = f"EMA compression / non-directional: EMA{fast_period}={curr_fast:.2f}, EMA{slow_period}={curr_slow:.2f}."

    if is_bullish_cross:
        explanation += f" [GOLDEN CROSSOVER: EMA{fast_period} crossed above EMA{slow_period}]"
    elif is_bearish_cross:
        explanation += f" [DEATH CROSSOVER: EMA{fast_period} crossed below EMA{slow_period}]"

    return EMAResult(
        ema_fast=curr_fast,
        ema_slow=curr_slow,
        prev_ema_fast=prev_fast,
        prev_ema_slow=prev_slow,
        current_close=curr_close,
        is_bullish_cross=is_bullish_cross,
        is_bearish_cross=is_bearish_cross,
        trend_alignment=trend_alignment,
        explanation=explanation
    )

