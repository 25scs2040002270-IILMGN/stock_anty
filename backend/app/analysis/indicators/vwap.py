from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import pandas as pd
import numpy as np


@dataclass
class VWAPResult:
    vwap: Optional[float]
    current_close: float
    distance_pct: float                 # % distance from VWAP: ((Close - VWAP) / VWAP) * 100
    is_above_vwap: bool
    is_bullish_cross: bool              # Crossed above VWAP on confirmed close
    is_bearish_cross: bool              # Crossed below VWAP on confirmed close
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vwap": round(self.vwap, 2) if self.vwap is not None else None,
            "distance_pct": round(self.distance_pct, 2),
            "is_above_vwap": self.is_above_vwap,
            "is_bullish_cross": self.is_bullish_cross,
            "is_bearish_cross": self.is_bearish_cross,
            "explanation": self.explanation
        }


def analyze_vwap(candles: List[Dict[str, Any]]) -> VWAPResult:
    """
    Calculates Intraday Session Volume Weighted Average Price (VWAP).
    Uses cumulative typical price * volume from the beginning of current trading session.
    """
    if not candles:
        return VWAPResult(
            vwap=None,
            current_close=0.0,
            distance_pct=0.0,
            is_above_vwap=False,
            is_bullish_cross=False,
            is_bearish_cross=False,
            explanation="Insufficient candle data for VWAP."
        )

    df = pd.DataFrame(candles)
    required = ["open_time", "high", "low", "close", "volume"]
    if not all(k in df.columns for k in required) or len(df) == 0:
        return VWAPResult(
            vwap=None,
            current_close=0.0,
            distance_pct=0.0,
            is_above_vwap=False,
            is_bullish_cross=False,
            is_bearish_cross=False,
            explanation="Missing required OHLCV columns for VWAP."
        )

    # Convert timestamps to IST calendar dates to identify session start
    # IST is UTC+05:30 (19800 seconds)
    df["session_day"] = (df["open_time"] + 19800) // 86400

    # Filter to current/latest session day
    latest_day = df["session_day"].iloc[-1]
    session_df = df[df["session_day"] == latest_day].copy()

    if len(session_df) == 0:
        session_df = df.copy()

    # Typical Price = (High + Low + Close) / 3
    session_df["tp"] = (session_df["high"] + session_df["low"] + session_df["close"]) / 3.0
    session_df["tpv"] = session_df["tp"] * session_df["volume"]

    cum_tpv = session_df["tpv"].cumsum()
    cum_vol = session_df["volume"].cumsum()

    # Avoid divide-by-zero if volume is 0
    vwap_series = np.where(cum_vol > 0, cum_tpv / cum_vol, session_df["tp"])
    session_df["vwap"] = vwap_series

    curr_close = float(session_df["close"].iloc[-1])
    curr_vwap = float(session_df["vwap"].iloc[-1])

    distance_pct = ((curr_close - curr_vwap) / curr_vwap) * 100.0 if curr_vwap > 0 else 0.0
    is_above = curr_close >= curr_vwap

    is_bullish_cross = False
    is_bearish_cross = False

    if len(session_df) >= 2:
        prev_close = float(session_df["close"].iloc[-2])
        prev_vwap = float(session_df["vwap"].iloc[-2])

        is_bullish_cross = (prev_close <= prev_vwap) and (curr_close > curr_vwap)
        is_bearish_cross = (prev_close >= prev_vwap) and (curr_close < curr_vwap)

    if is_bullish_cross:
        status_text = f"Bullish breakout above VWAP ({curr_close:.2f} > {curr_vwap:.2f})"
    elif is_bearish_cross:
        status_text = f"Bearish breakdown below VWAP ({curr_close:.2f} < {curr_vwap:.2f})"
    elif is_above:
        status_text = f"Trading above VWAP (+{distance_pct:.2f}% above session mean)"
    else:
        status_text = f"Trading below VWAP ({distance_pct:.2f}% below session mean)"

    explanation = f"Session VWAP is ₹{curr_vwap:.2f}. Current price ₹{curr_close:.2f}: {status_text}."

    return VWAPResult(
        vwap=curr_vwap,
        current_close=curr_close,
        distance_pct=distance_pct,
        is_above_vwap=is_above,
        is_bullish_cross=is_bullish_cross,
        is_bearish_cross=is_bearish_cross,
        explanation=explanation
    )

