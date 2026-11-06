from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np
from app.analysis.indicators.market_structure import detect_swing_points, SwingPoint


@dataclass
class SRZone:
    zone_type: str                      # 'SUPPORT' or 'RESISTANCE'
    level_center: float
    level_low: float
    level_high: float
    touches: int
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_type": self.zone_type,
            "level_center": round(self.level_center, 2),
            "level_low": round(self.level_low, 2),
            "level_high": round(self.level_high, 2),
            "touches": self.touches
        }


@dataclass
class SupportResistanceResult:
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    support_zones: List[SRZone]
    resistance_zones: List[SRZone]
    is_at_support: bool
    is_at_resistance: bool
    is_breakout_above: bool             # Close broke above immediate resistance
    is_breakout_below: bool             # Close broke below immediate support
    is_retest: bool                     # Pullback retesting broken level
    is_rejection: bool                  # Wick rejection at zone
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nearest_support": round(self.nearest_support, 2) if self.nearest_support else None,
            "nearest_resistance": round(self.nearest_resistance, 2) if self.nearest_resistance else None,
            "is_at_support": self.is_at_support,
            "is_at_resistance": self.is_at_resistance,
            "is_breakout_above": self.is_breakout_above,
            "is_breakout_below": self.is_breakout_below,
            "is_retest": self.is_retest,
            "is_rejection": self.is_rejection,
            "explanation": self.explanation
        }


def cluster_levels_into_zones(
    prices: List[float],
    zone_type: str,
    tolerance_pct: float = 0.25
) -> List[SRZone]:
    """
    Groups individual swing prices into meaningful S/R zones.
    tolerance_pct: e.g. 0.25% distance creates a zone band.
    """
    if not prices:
        return []

    sorted_p = sorted(prices)
    clusters: List[List[float]] = []

    for p in sorted_p:
        added = False
        for c in clusters:
            center = sum(c) / len(c)
            diff_pct = abs(p - center) / center * 100.0
            if diff_pct <= tolerance_pct:
                c.append(p)
                added = True
                break
        if not added:
            clusters.append([p])

    zones: List[SRZone] = []
    for c in clusters:
        center = float(sum(c) / len(c))
        half_band = center * (tolerance_pct / 100.0)
        zones.append(SRZone(
            zone_type=zone_type,
            level_center=center,
            level_low=center - half_band,
            level_high=center + half_band,
            touches=len(c)
        ))

    # Sort resistance ascending, support descending
    if zone_type == "SUPPORT":
        zones.sort(key=lambda z: z.level_center, reverse=True)
    else:
        zones.sort(key=lambda z: z.level_center, reverse=False)

    return zones


def analyze_support_resistance(
    candles: List[Dict[str, Any]],
    tolerance_pct: float = 0.25
) -> SupportResistanceResult:
    """
    Extracts high-probability Support & Resistance zones from swing points.
    Identifies breakout, retest, and rejection events relative to current close.
    """
    if not candles:
        return SupportResistanceResult(
            nearest_support=None,
            nearest_resistance=None,
            support_zones=[],
            resistance_zones=[],
            is_at_support=False,
            is_at_resistance=False,
            is_breakout_above=False,
            is_breakout_below=False,
            is_retest=False,
            is_rejection=False,
            explanation="Insufficient candle data for Support/Resistance."
        )

    df = pd.DataFrame(candles)
    curr_close = float(df["close"].iloc[-1])
    curr_high = float(df["high"].iloc[-1])
    curr_low = float(df["low"].iloc[-1])
    curr_open = float(df["open"].iloc[-1])

    swing_points = detect_swing_points(candles, order=2)

    high_prices = [p.price for p in swing_points if p.type == "SWING_HIGH"]
    low_prices = [p.price for p in swing_points if p.type == "SWING_LOW"]

    # If too few swing points, supplement with prior candle extremes
    if len(high_prices) < 2 and len(df) >= 2:
        prior_highs = df["high"].iloc[:-1].nlargest(min(3, len(df)-1)).tolist()
        high_prices.extend(prior_highs)
    if len(low_prices) < 2 and len(df) >= 2:
        prior_lows = df["low"].iloc[:-1].nsmallest(min(3, len(df)-1)).tolist()
        low_prices.extend(prior_lows)

    res_zones = cluster_levels_into_zones(high_prices, zone_type="RESISTANCE", tolerance_pct=tolerance_pct)
    sup_zones = cluster_levels_into_zones(low_prices, zone_type="SUPPORT", tolerance_pct=tolerance_pct)

    # Nearest resistance: closest zone center to current price
    if res_zones:
        nearest_res = sorted(res_zones, key=lambda z: abs(z.level_center - curr_close))[0].level_center
    elif high_prices:
        nearest_res = sorted(high_prices, key=lambda p: abs(p - curr_close))[0]
    else:
        nearest_res = None

    # Nearest support: closest zone center to current price
    if sup_zones:
        nearest_sup = sorted(sup_zones, key=lambda z: abs(z.level_center - curr_close))[0].level_center
    elif low_prices:
        nearest_sup = sorted(low_prices, key=lambda p: abs(p - curr_close))[0]
    else:
        nearest_sup = None

    # Test proximity
    is_at_res = False
    if nearest_res:
        dist_res_pct = (nearest_res - curr_close) / curr_close * 100.0
        is_at_res = -0.15 <= dist_res_pct <= 0.35

    is_at_sup = False
    if nearest_sup:
        dist_sup_pct = (curr_close - nearest_sup) / curr_close * 100.0
        is_at_sup = -0.15 <= dist_sup_pct <= 0.35

    # Breakout & retest checks across recent 2 bars
    is_breakout_above = False
    is_breakout_below = False
    is_retest = False
    is_rejection = False

    if len(df) >= 2 and nearest_res:
        prev_close = float(df["close"].iloc[-2])
        if prev_close <= nearest_res and curr_close > nearest_res:
            is_breakout_above = True

    if len(df) >= 2 and nearest_sup:
        prev_close = float(df["close"].iloc[-2])
        if prev_close >= nearest_sup and curr_close < nearest_sup:
            is_breakout_below = True

    # Rejection: Upper wick at resistance or lower wick at support
    body = abs(curr_close - curr_open)
    upper_wick = curr_high - max(curr_close, curr_open)
    lower_wick = min(curr_close, curr_open) - curr_low

    if is_at_res and upper_wick >= body * 1.5:
        is_rejection = True
    elif is_at_sup and lower_wick >= body * 1.5:
        is_rejection = True

    # Retest check: broke out on previous bar, current bar tested level and held
    if len(df) >= 3 and nearest_sup:
        two_bars_ago_c = float(df["close"].iloc[-3])
        one_bar_ago_c = float(df["close"].iloc[-2])
        if two_bars_ago_c <= nearest_sup and one_bar_ago_c > nearest_sup and curr_low <= nearest_sup * 1.002 and curr_close > nearest_sup:
            is_retest = True

    sup_str = f"₹{nearest_sup:.2f}" if nearest_sup else "None"
    res_str = f"₹{nearest_res:.2f}" if nearest_res else "None"
    explanation = f"Nearest Support: {sup_str}, Nearest Resistance: {res_str}."

    if is_breakout_above:
        explanation += " [BULLISH BREAKOUT above resistance confirmed]"
    elif is_breakout_below:
        explanation += " [BEARISH BREAKDOWN below support confirmed]"
    elif is_retest:
        explanation += " [BULLISH RETEST of broken resistance holding as support]"
    elif is_rejection:
        explanation += " [PRICE REJECTION: long wick at key zone]"
    elif is_at_sup:
        explanation += " [AT SUPPORT ZONE: monitoring for buyer defense]"
    elif is_at_res:
        explanation += " [AT RESISTANCE ZONE: monitoring for seller supply]"

    return SupportResistanceResult(
        nearest_support=nearest_sup,
        nearest_resistance=nearest_res,
        support_zones=sup_zones,
        resistance_zones=res_zones,
        is_at_support=is_at_sup,
        is_at_resistance=is_at_res,
        is_breakout_above=is_breakout_above,
        is_breakout_below=is_breakout_below,
        is_retest=is_retest,
        is_rejection=is_rejection,
        explanation=explanation
    )
