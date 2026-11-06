from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np


@dataclass
class VolumeResult:
    current_volume: int
    average_volume: float               # 20-period SMA
    relative_volume: float              # RVOL = Volume / Avg Volume
    is_expansion: bool                  # RVOL >= 1.5
    is_contraction: bool                # RVOL <= 0.7
    is_confirmed: bool                  # Volume confirms price move direction
    volume_trend: str                   # 'EXPANDING', 'NORMAL', 'CONTRACTING'
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_volume": self.current_volume,
            "average_volume": round(self.average_volume, 0),
            "relative_volume": round(self.relative_volume, 2),
            "is_expansion": self.is_expansion,
            "is_contraction": self.is_contraction,
            "is_confirmed": self.is_confirmed,
            "volume_trend": self.volume_trend,
            "explanation": self.explanation
        }


def analyze_volume(candles: List[Dict[str, Any]], sma_period: int = 20) -> VolumeResult:
    """
    Analyzes candle volume dynamics:
    - 20-period volume SMA
    - Relative volume (RVOL)
    - Volume expansion and contraction
    - Directional confirmation with price action
    """
    if not candles:
        return VolumeResult(
            current_volume=0,
            average_volume=0.0,
            relative_volume=0.0,
            is_expansion=False,
            is_contraction=False,
            is_confirmed=False,
            volume_trend="CONTRACTING",
            explanation="Insufficient candle volume data."
        )

    df = pd.DataFrame(candles)
    if "volume" not in df.columns or len(df) == 0:
        return VolumeResult(
            current_volume=0,
            average_volume=0.0,
            relative_volume=0.0,
            is_expansion=False,
            is_contraction=False,
            is_confirmed=False,
            volume_trend="CONTRACTING",
            explanation="Missing volume data."
        )

    vol_series = df["volume"].astype(float)
    curr_vol = int(vol_series.iloc[-1])

    # Volume SMA over available periods up to sma_period
    window = min(len(vol_series), sma_period)
    avg_vol = float(vol_series.iloc[-window:].mean()) if window > 0 else float(curr_vol)
    if avg_vol <= 0:
        avg_vol = 1.0  # Guard against divide by zero

    rvol = curr_vol / avg_vol

    is_expansion = rvol >= 1.5
    is_contraction = rvol <= 0.7

    if is_expansion:
        volume_trend = "EXPANDING"
    elif is_contraction:
        volume_trend = "CONTRACTING"
    else:
        volume_trend = "NORMAL"

    # Directional confirmation:
    # A bullish candle with above-average volume (RVOL >= 1.0) is confirmed.
    # An up move on tiny volume (RVOL < 0.7) lacks institutional backing.
    is_up_candle = False
    if "open" in df.columns and "close" in df.columns:
        is_up_candle = float(df["close"].iloc[-1]) >= float(df["open"].iloc[-1])

    is_confirmed = rvol >= 1.0

    if is_expansion:
        cond_text = f"Significant volume expansion ({rvol:.2f}x of 20-bar average {avg_vol:.0f})"
    elif is_contraction:
        cond_text = f"Volume contraction ({rvol:.2f}x of average {avg_vol:.0f}), cautious participation"
    else:
        cond_text = f"Normal volume ({rvol:.2f}x average)"

    candle_dir = "bullish" if is_up_candle else "bearish"
    explanation = f"{curr_vol:,} shares traded on latest {candle_dir} candle: {cond_text}."

    return VolumeResult(
        current_volume=curr_vol,
        average_volume=avg_vol,
        relative_volume=rvol,
        is_expansion=is_expansion,
        is_contraction=is_contraction,
        is_confirmed=is_confirmed,
        volume_trend=volume_trend,
        explanation=explanation
    )

