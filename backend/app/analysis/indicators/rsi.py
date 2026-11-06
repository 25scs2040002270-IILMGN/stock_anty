from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np


@dataclass
class RSIResult:
    rsi: Optional[float]
    prev_rsi: Optional[float]
    momentum: str                       # 'BULLISH', 'BEARISH', 'NEUTRAL'
    is_overbought: bool                 # RSI >= 70
    is_oversold: bool                   # RSI <= 30
    divergence: Optional[str]           # 'BULLISH_DIVERGENCE', 'BEARISH_DIVERGENCE', None
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rsi": round(self.rsi, 2) if self.rsi is not None else None,
            "momentum": self.momentum,
            "is_overbought": self.is_overbought,
            "is_oversold": self.is_oversold,
            "divergence": self.divergence,
            "explanation": self.explanation
        }


def calculate_rsi_series(close_series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Wilder's Smoothed Relative Strength Index (RSI)."""
    if len(close_series) < period + 1:
        return pd.Series(index=close_series.index, dtype=float)

    delta = close_series.diff()
    gain = delta.clip(lower=0.0)
    loss = -1.0 * delta.clip(upper=0.0)

    # First average: SMA
    avg_gain = gain.iloc[1:period + 1].mean()
    avg_loss = loss.iloc[1:period + 1].mean()

    rsi_values = [np.nan] * period

    if avg_loss == 0.0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    # Subsequent values using Wilder's smoothing: alpha = 1 / period
    for i in range(period + 1, len(close_series)):
        g = gain.iloc[i]
        l = loss.iloc[i]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

        if avg_loss == 0.0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return pd.Series(rsi_values, index=close_series.index)


def detect_rsi_divergence(
    prices: pd.Series,
    rsis: pd.Series,
    lookback: int = 25
) -> Tuple[Optional[str], str]:
    """
    Detects regular Bullish and Bearish RSI divergences over recent swings.
    - Bullish: Price Lower Low while RSI Higher Low.
    - Bearish: Price Higher High while RSI Lower High.
    """
    if len(prices) < 10 or len(rsis.dropna()) < 10:
        return None, ""

    window_p = prices.iloc[-lookback:]
    window_r = rsis.iloc[-lookback:]

    # Find swing lows for bullish divergence (comparing recent low to prior low)
    # Check if latest candle or 1-2 bars ago is a swing low
    recent_idx = -1
    min_idx = window_p.iloc[:-3].idxmin() if len(window_p) > 5 else None

    # Check Bullish Divergence: Price making new low but RSI higher
    if min_idx is not None:
        p_prior_min = window_p.loc[min_idx]
        r_prior_min = window_r.loc[min_idx]
        p_recent = window_p.iloc[-1]
        r_recent = window_r.iloc[-1]

        if p_recent < p_prior_min and r_recent > r_prior_min and r_recent < 45.0:
            return "BULLISH_DIVERGENCE", f"Bullish divergence: Price made lower low ({p_recent:.2f} < {p_prior_min:.2f}) while RSI formed higher low ({r_recent:.1f} > {r_prior_min:.1f})."

    # Check Bearish Divergence: Price making new high but RSI lower
    max_idx = window_p.iloc[:-3].idxmax() if len(window_p) > 5 else None
    if max_idx is not None:
        p_prior_max = window_p.loc[max_idx]
        r_prior_max = window_r.loc[max_idx]
        p_recent = window_p.iloc[-1]
        r_recent = window_r.iloc[-1]

        if p_recent > p_prior_max and r_recent < r_prior_max and r_recent > 55.0:
            return "BEARISH_DIVERGENCE", f"Bearish divergence: Price made higher high ({p_recent:.2f} > {p_prior_max:.2f}) while RSI formed lower high ({r_recent:.1f} < {r_prior_max:.1f})."

    return None, ""


def analyze_rsi(candles: List[Dict[str, Any]], period: int = 14) -> RSIResult:
    """Analyzes RSI 14, overbought/oversold levels, momentum direction, and divergence."""
    if not candles:
        return RSIResult(
            rsi=None,
            prev_rsi=None,
            momentum="NEUTRAL",
            is_overbought=False,
            is_oversold=False,
            divergence=None,
            explanation="Insufficient candle data for RSI."
        )

    df = pd.DataFrame(candles)
    if "close" not in df.columns or len(df) < period + 1:
        return RSIResult(
            rsi=None,
            prev_rsi=None,
            momentum="NEUTRAL",
            is_overbought=False,
            is_oversold=False,
            divergence=None,
            explanation=f"Need at least {period + 1} completed candles for RSI{period} (have {len(df)})."
        )

    close_series = df["close"].astype(float)
    rsi_s = calculate_rsi_series(close_series, period=period)

    curr_rsi = float(rsi_s.iloc[-1])
    prev_rsi = float(rsi_s.iloc[-2]) if len(rsi_s) > 1 and not np.isnan(rsi_s.iloc[-2]) else curr_rsi

    is_ob = curr_rsi >= 70.0
    is_os = curr_rsi <= 30.0

    # Momentum direction:
    # Bullish momentum: RSI > 50 and rising
    # Bearish momentum: RSI < 50 and falling
    if curr_rsi >= 50.0:
        if curr_rsi >= prev_rsi:
            momentum = "BULLISH"
            mom_desc = "bullish momentum expanding (RSI > 50 & rising)"
        else:
            momentum = "NEUTRAL"
            mom_desc = "bullish momentum cooling (RSI > 50 but softening)"
    else:
        if curr_rsi <= prev_rsi:
            momentum = "BEARISH"
            mom_desc = "bearish momentum expanding (RSI < 50 & falling)"
        else:
            momentum = "NEUTRAL"
            mom_desc = "bearish momentum slowing (RSI < 50 but ticking up)"

    divergence, div_desc = detect_rsi_divergence(close_series, rsi_s)

    explanation = f"RSI{period} at {curr_rsi:.1f} ({mom_desc})."
    if is_ob:
        explanation += " [OVERBOUGHT >= 70: upside exhaustion risk]"
    elif is_os:
        explanation += " [OVERSOLD <= 30: downside exhaustion risk]"

    if divergence:
        explanation += f" [{div_desc}]"

    return RSIResult(
        rsi=curr_rsi,
        prev_rsi=prev_rsi,
        momentum=momentum,
        is_overbought=is_ob,
        is_oversold=is_os,
        divergence=divergence,
        explanation=explanation
    )

