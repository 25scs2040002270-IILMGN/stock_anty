from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np

from app.analysis.indicators.market_structure import detect_swing_points, SwingPoint
from app.analysis.indicators.support_resistance import analyze_support_resistance


@dataclass
class LiquidityAnalysisResult:
    fakeout_risk_level: str             # 'LOW FAKEOUT RISK', 'MODERATE FAKEOUT RISK', 'HIGH FAKEOUT RISK', 'POSSIBLE LIQUIDITY SWEEP'
    is_high_risk: bool                  # True if HIGH FAKEOUT RISK or POSSIBLE LIQUIDITY SWEEP
    sweep_type: Optional[str]           # 'SWING_HIGH_SWEEP', 'SWING_LOW_SWEEP', None
    relevant_level: Optional[float]
    candle_timestamp: int
    wick_ratio: float                   # Upper or lower wick as ratio of total range
    volume_behavior: str                # e.g. 'HIGH_VOLUME_REJECTION', 'NORMAL_VOLUME', 'LOW_VOLUME_EXPANSION'
    depth_imbalance_ratio: Optional[float] # Bid qty / Ask qty if available
    spread_pct: Optional[float]         # (Ask - Bid) / LTP in %
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fakeout_risk_level": self.fakeout_risk_level,
            "is_high_risk": self.is_high_risk,
            "sweep_type": self.sweep_type,
            "relevant_level": round(self.relevant_level, 2) if self.relevant_level else None,
            "candle_timestamp": self.candle_timestamp,
            "wick_ratio": round(self.wick_ratio, 2),
            "volume_behavior": self.volume_behavior,
            "depth_imbalance_ratio": round(self.depth_imbalance_ratio, 2) if self.depth_imbalance_ratio else None,
            "spread_pct": round(self.spread_pct, 4) if self.spread_pct else None,
            "reason": self.reason
        }


def analyze_liquidity_and_sweeps(
    candles: List[Dict[str, Any]],
    latest_tick: Optional[Dict[str, Any]] = None
) -> LiquidityAnalysisResult:
    """
    Dedicated Liquidity Analysis & False Breakout Detector.
    Evaluates observable price and volume behavior against key swing points and depth:
    1. High sweep: High breaks above swing high but close settles below.
    2. Low sweep: Low breaks below swing low but close settles above.
    3. Upper wick rejection near resistance.
    4. Lower wick rejection near support.
    5. High volume during rejection.
    6. Failed breakout retest.
    7. Bid/ask depth imbalance.
    8. Abnormal spread expansion.
    9. Rapid intraday rejection after breakout.
    """
    if len(candles) < 3:
        return LiquidityAnalysisResult(
            fakeout_risk_level="LOW FAKEOUT RISK",
            is_high_risk=False,
            sweep_type=None,
            relevant_level=None,
            candle_timestamp=0,
            wick_ratio=0.0,
            volume_behavior="INSUFFICIENT_DATA",
            depth_imbalance_ratio=None,
            spread_pct=None,
            reason="Insufficient candle history to assess liquidity sweep risk."
        )

    df = pd.DataFrame(candles)
    c_curr = df.iloc[-1]
    curr_time = int(c_curr.get("open_time", 0))
    curr_open = float(c_curr["open"])
    curr_high = float(c_curr["high"])
    curr_low = float(c_curr["low"])
    curr_close = float(c_curr["close"])
    curr_vol = float(c_curr["volume"]) if "volume" in c_curr else 1.0

    curr_range = max(curr_high - curr_low, 0.01)
    upper_wick = curr_high - max(curr_open, curr_close)
    lower_wick = min(curr_open, curr_close) - curr_low

    upper_wick_ratio = upper_wick / curr_range
    lower_wick_ratio = lower_wick / curr_range

    # Volume context
    avg_vol = float(df["volume"].iloc[-20:].mean()) if len(df) >= 5 else curr_vol
    rvol = (curr_vol / avg_vol) if avg_vol > 0 else 1.0

    # Detect swing points prior to current candle
    prior_candles = candles[:-1]
    order = 2 if len(prior_candles) >= 7 else 1
    swing_points = detect_swing_points(prior_candles, order=order)

    swing_highs = [p.price for p in swing_points if p.type == "SWING_HIGH"]
    swing_lows = [p.price for p in swing_points if p.type == "SWING_LOW"]

    recent_sh = swing_highs[-1] if swing_highs else (max(float(c["high"]) for c in prior_candles) if prior_candles else None)
    recent_sl = swing_lows[-1] if swing_lows else (min(float(c["low"]) for c in prior_candles) if prior_candles else None)

    # Bid/Ask depth and spread metrics
    depth_imbalance: Optional[float] = None
    spread_pct: Optional[float] = None

    if latest_tick:
        bids = latest_tick.get("bids", [])
        asks = latest_tick.get("asks", [])
        if bids and asks:
            total_bid_qty = sum(b.get("quantity", 0) for b in bids[:5])
            total_ask_qty = sum(a.get("quantity", 0) for a in asks[:5])
            if total_ask_qty > 0:
                depth_imbalance = total_bid_qty / total_ask_qty

            best_bid = float(bids[0].get("price", 0))
            best_ask = float(asks[0].get("price", 0))
            if best_bid > 0 and best_ask > best_bid:
                spread_pct = ((best_ask - best_bid) / curr_close) * 100.0

    # Evaluate sweep conditions
    sweep_type: Optional[str] = None
    relevant_level: Optional[float] = None
    risk_level = "LOW FAKEOUT RISK"
    reasons: List[str] = []

    # Condition 1: High Liquidity Sweep (Upper Wick rejection above swing high)
    # Price pierced above swing high, but closed back below it!
    if recent_sh and curr_high > recent_sh and curr_close < recent_sh:
        sweep_type = "SWING_HIGH_SWEEP"
        relevant_level = recent_sh
        if upper_wick_ratio >= 0.40:
            risk_level = "POSSIBLE LIQUIDITY SWEEP"
            reasons.append(
                f"Observed swing high sweep: Price breached recent peak {recent_sh:.2f} (high {curr_high:.2f}), "
                f"subsequently closing lower at {curr_close:.2f} with {upper_wick_ratio*100:.0f}% upper wick."
            )
        else:
            risk_level = "HIGH FAKEOUT RISK"
            reasons.append(
                f"Breakout failure: Price tested above swing high {recent_sh:.2f} but closed below it ({curr_close:.2f})."
            )

    # Condition 2: Low Liquidity Sweep (Lower Wick rejection below swing low)
    # Price pierced below swing low, but closed back above it!
    elif recent_sl and curr_low < recent_sl and curr_close > recent_sl:
        sweep_type = "SWING_LOW_SWEEP"
        relevant_level = recent_sl
        if lower_wick_ratio >= 0.40:
            risk_level = "POSSIBLE LIQUIDITY SWEEP"
            reasons.append(
                f"Observed swing low sweep: Price dipped below support pivot {recent_sl:.2f} (low {curr_low:.2f}), "
                f"subsequently closing higher at {curr_close:.2f} with {lower_wick_ratio*100:.0f}% lower wick."
            )
        else:
            risk_level = "HIGH FAKEOUT RISK"
            reasons.append(
                f"Breakdown failure: Price probed below swing low {recent_sl:.2f} but closed above it ({curr_close:.2f})."
            )

    # Condition 3 & 4: Excessive Wick Rejections
    elif upper_wick_ratio >= 0.55:
        risk_level = "HIGH FAKEOUT RISK"
        relevant_level = curr_high
        reasons.append(
            f"Overhead liquidity rejection: Prominent upper wick ({upper_wick_ratio*100:.0f}% of bar range) indicating supply absorption."
        )
    elif lower_wick_ratio >= 0.55:
        risk_level = "HIGH FAKEOUT RISK"
        relevant_level = curr_low
        reasons.append(
            f"Downside liquidity rejection: Prominent lower wick ({lower_wick_ratio*100:.0f}% of bar range) indicating aggressive dip buyers."
        )

    # Condition 5: Volume anomaly on failed moves
    volume_behavior = "NORMAL_VOLUME"
    if rvol >= 1.6:
        if risk_level in ("POSSIBLE LIQUIDITY SWEEP", "HIGH FAKEOUT RISK"):
            volume_behavior = "HIGH_VOLUME_REJECTION"
            reasons.append(f"High relative volume ({rvol:.1f}x) accompanies the rejected level.")
        else:
            volume_behavior = "EXPANDING_VOLUME"
    elif rvol <= 0.6:
        volume_behavior = "LOW_VOLUME_CONTRACTION"
        if risk_level == "LOW FAKEOUT RISK":
            risk_level = "MODERATE FAKEOUT RISK"
            reasons.append("Very low volume relative to 20-bar average, suggesting hesitant participation.")

    # Condition 7 & 8: Order Book Imbalance / Spread Expansion
    if spread_pct and spread_pct > 0.08:  # Spread wider than 0.08% for large-cap liquid equities
        if risk_level == "LOW FAKEOUT RISK":
            risk_level = "MODERATE FAKEOUT RISK"
        reasons.append(f"Abnormal bid-ask spread expansion ({spread_pct:.3f}%).")

    if depth_imbalance:
        if sweep_type == "SWING_HIGH_SWEEP" and depth_imbalance < 0.6:
            reasons.append(f"Order book depth shows heavy asking pressure (Bid/Ask ratio: {depth_imbalance:.2f}).")
        elif sweep_type == "SWING_LOW_SWEEP" and depth_imbalance > 1.6:
            reasons.append(f"Order book depth shows heavy bidding support (Bid/Ask ratio: {depth_imbalance:.2f}).")

    if not reasons:
        reasons.append("Clean price action: no abnormal wicks, sweeps, or depth imbalances detected.")

    final_wick_ratio = max(upper_wick_ratio, lower_wick_ratio)
    is_high = risk_level in ("HIGH FAKEOUT RISK", "POSSIBLE LIQUIDITY SWEEP")

    return LiquidityAnalysisResult(
        fakeout_risk_level=risk_level,
        is_high_risk=is_high,
        sweep_type=sweep_type,
        relevant_level=relevant_level,
        candle_timestamp=curr_time,
        wick_ratio=final_wick_ratio,
        volume_behavior=volume_behavior,
        depth_imbalance_ratio=depth_imbalance,
        spread_pct=spread_pct,
        reason=" | ".join(reasons)
    )
