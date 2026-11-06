from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np


@dataclass
class SwingPoint:
    index: int
    open_time: int
    price: float
    type: str                           # 'SWING_HIGH' or 'SWING_LOW'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "open_time": self.open_time,
            "price": round(self.price, 2),
            "type": self.type
        }


@dataclass
class MarketStructureResult:
    structure: str                      # 'BULLISH', 'BEARISH', 'SIDEWAYS'
    recent_swing_high: Optional[float]
    recent_swing_low: Optional[float]
    prior_swing_high: Optional[float]
    prior_swing_low: Optional[float]
    has_higher_highs: bool
    has_higher_lows: bool
    has_lower_highs: bool
    has_lower_lows: bool
    swing_points: List[SwingPoint]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structure": self.structure,
            "recent_swing_high": round(self.recent_swing_high, 2) if self.recent_swing_high else None,
            "recent_swing_low": round(self.recent_swing_low, 2) if self.recent_swing_low else None,
            "has_higher_highs": self.has_higher_highs,
            "has_higher_lows": self.has_higher_lows,
            "has_lower_highs": self.has_lower_highs,
            "has_lower_lows": self.has_lower_lows,
            "explanation": self.explanation
        }


def detect_swing_points(candles: List[Dict[str, Any]], order: int = 2) -> List[SwingPoint]:
    """
    Identifies fractal swing points using local extrema:
    A Swing High has High >= previous `order` highs and >= subsequent `order` highs.
    A Swing Low has Low <= previous `order` lows and <= subsequent `order` lows.
    """
    if len(candles) < (order * 2 + 1):
        return []

    df = pd.DataFrame(candles)
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    times = df["open_time"].values if "open_time" in df.columns else np.zeros(len(df))

    swing_points: List[SwingPoint] = []
    n = len(df)

    for i in range(order, n - order):
        # Swing High
        is_high = True
        for offset in range(1, order + 1):
            if highs[i] < highs[i - offset] or highs[i] < highs[i + offset]:
                is_high = False
                break
        if is_high:
            swing_points.append(SwingPoint(
                index=i,
                open_time=int(times[i]),
                price=float(highs[i]),
                type="SWING_HIGH"
            ))

        # Swing Low
        is_low = True
        for offset in range(1, order + 1):
            if lows[i] > lows[i - offset] or lows[i] > lows[i + offset]:
                is_low = False
                break
        if is_low:
            swing_points.append(SwingPoint(
                index=i,
                open_time=int(times[i]),
                price=float(lows[i]),
                type="SWING_LOW"
            ))

    return swing_points


def analyze_market_structure(candles: List[Dict[str, Any]], order: int = 2) -> MarketStructureResult:
    """
    Classifies Market Structure based on swing point progression:
    - Higher Highs (HH) + Higher Lows (HL) -> BULLISH
    - Lower Highs (LH) + Lower Lows (LL) -> BEARISH
    - Conflicting / Choppy -> SIDEWAYS
    """
    if not candles or len(candles) < (order * 2 + 1):
        return MarketStructureResult(
            structure="SIDEWAYS",
            recent_swing_high=None,
            recent_swing_low=None,
            prior_swing_high=None,
            prior_swing_low=None,
            has_higher_highs=False,
            has_higher_lows=False,
            has_lower_highs=False,
            has_lower_lows=False,
            swing_points=[],
            explanation="Insufficient candles to establish swing points."
        )

    points = detect_swing_points(candles, order=order)

    high_points = [p for p in points if p.type == "SWING_HIGH"]
    low_points = [p for p in points if p.type == "SWING_LOW"]

    recent_sh = high_points[-1].price if len(high_points) >= 1 else None
    prior_sh = high_points[-2].price if len(high_points) >= 2 else None

    recent_sl = low_points[-1].price if len(low_points) >= 1 else None
    prior_sl = low_points[-2].price if len(low_points) >= 2 else None

    has_hh = (recent_sh is not None and prior_sh is not None) and (recent_sh > prior_sh)
    has_lh = (recent_sh is not None and prior_sh is not None) and (recent_sh < prior_sh)
    has_hl = (recent_sl is not None and prior_sl is not None) and (recent_sl > prior_sl)
    has_ll = (recent_sl is not None and prior_sl is not None) and (recent_sl < prior_sl)

    # Classification
    if has_hh and has_hl:
        structure = "BULLISH"
        explanation = f"Bullish structure: Higher Highs ({recent_sh:.2f} > {prior_sh:.2f}) and Higher Lows ({recent_sl:.2f} > {prior_sl:.2f})."
    elif has_lh and has_ll:
        structure = "BEARISH"
        explanation = f"Bearish structure: Lower Highs ({recent_sh:.2f} < {prior_sh:.2f}) and Lower Lows ({recent_sl:.2f} < {prior_sl:.2f})."
    elif has_hh and not has_hl:
        structure = "SIDEWAYS"
        explanation = f"Expanding/neutral range: Recent high formed Higher High ({recent_sh:.2f}) without Higher Low confirmation."
    elif has_ll and not has_lh:
        structure = "SIDEWAYS"
        explanation = f"Compromised structure: Recent low breached Lower Low ({recent_sl:.2f}) without Lower High confirmation."
    else:
        # Fallback if too few confirmed swing pivots: evaluate recent high/low range
        highs = [float(c["high"]) for c in candles[-10:] if "high" in c]
        lows = [float(c["low"]) for c in candles[-10:] if "low" in c]
        if highs and lows:
            recent_sh = recent_sh or max(highs)
            recent_sl = recent_sl or min(lows)
        structure = "SIDEWAYS"
        explanation = "Sideways consolidation / consolidating within recent swing range."

    return MarketStructureResult(
        structure=structure,
        recent_swing_high=recent_sh,
        recent_swing_low=recent_sl,
        prior_swing_high=prior_sh,
        prior_swing_low=prior_sl,
        has_higher_highs=has_hh,
        has_higher_lows=has_hl,
        has_lower_highs=has_lh,
        has_lower_lows=has_ll,
        swing_points=points,
        explanation=explanation
    )

