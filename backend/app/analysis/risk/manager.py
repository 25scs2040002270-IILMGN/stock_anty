import math
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple


@dataclass
class RiskProfile:
    entry_price: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    target: float
    risk_reward_ratio: float
    risk_amount: float                  # Maximum currency risk (INR)
    suggested_shares: int               # Number of shares based on capital & risk %
    monetary_risk_actual: float         # shares * |entry - stop_loss|
    potential_profit: float             # shares * |target - entry|
    trading_capital: float
    risk_percentage: float
    is_valid_rr: bool                   # True if R:R >= minimum required (e.g. 1.5)
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_price": round(self.entry_price, 2),
            "entry_zone": {
                "low": round(self.entry_zone_low, 2),
                "high": round(self.entry_zone_high, 2)
            },
            "stop_loss": round(self.stop_loss, 2),
            "target": round(self.target, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "risk_amount_budget": round(self.risk_amount, 2),
            "suggested_shares": self.suggested_shares,
            "monetary_risk_actual": round(self.monetary_risk_actual, 2),
            "potential_profit": round(self.potential_profit, 2),
            "trading_capital": self.trading_capital,
            "risk_percentage": self.risk_percentage,
            "is_valid_rr": self.is_valid_rr,
            "explanation": self.explanation
        }


class RiskManager:
    """
    Dedicated Quantitative Risk Management Engine.
    Calculates entry zones, stop losses, profit targets, R:R ratios,
    and mathematically sound position sizing adhering strictly to account capital.
    """

    def __init__(
        self,
        trading_capital: float = 100000.0,
        risk_percentage: float = 1.0,
        min_rr_ratio: float = 1.5,
        lot_size: int = 1
    ) -> None:
        self.trading_capital = max(1000.0, float(trading_capital))
        self.risk_percentage = max(0.1, min(10.0, float(risk_percentage)))
        self.min_rr_ratio = float(min_rr_ratio)
        self.lot_size = max(1, int(lot_size))

    def calculate_trade_risk(
        self,
        symbol: str,
        direction: str,  # 'BUY' or 'SELL'
        current_price: float,
        structure_stop: Optional[float] = None,
        structure_target: Optional[float] = None,
        capital_override: Optional[float] = None,
        risk_pct_override: Optional[float] = None
    ) -> RiskProfile:
        capital = capital_override if capital_override is not None else self.trading_capital
        risk_pct = risk_pct_override if risk_pct_override is not None else self.risk_percentage

        entry_price = round(current_price, 2)

        # Entry zone is a tight ±0.08% band around current execution price
        entry_zone_low = round(entry_price * 0.9992, 2)
        entry_zone_high = round(entry_price * 1.0008, 2)

        # Calculate Stop Loss
        # For BUY: stop loss below recent swing low or minimum 0.4% default
        # For SELL: stop loss above recent swing high or minimum 0.4% default
        if direction.upper() == "BUY":
            if structure_stop and structure_stop < entry_price:
                # Add 0.05 buffer below swing low
                stop_loss = round(structure_stop - 0.10, 2)
            else:
                stop_loss = round(entry_price * 0.995, 2)  # Default 0.5% stop

            risk_per_share = max(entry_price - stop_loss, 0.10)

            # Target: structure resistance or 2x risk
            if structure_target and structure_target > entry_price and (structure_target - entry_price) >= (risk_per_share * self.min_rr_ratio):
                target = round(structure_target, 2)
            else:
                target = round(entry_price + (risk_per_share * 2.0), 2)  # 1:2 R:R default

            reward_per_share = target - entry_price

        else:  # SELL / Bearish
            if structure_stop and structure_stop > entry_price:
                stop_loss = round(structure_stop + 0.10, 2)
            else:
                stop_loss = round(entry_price * 1.005, 2)

            risk_per_share = max(stop_loss - entry_price, 0.10)

            if structure_target and structure_target < entry_price and (entry_price - structure_target) >= (risk_per_share * self.min_rr_ratio):
                target = round(structure_target, 2)
            else:
                target = round(entry_price - (risk_per_share * 2.0), 2)

            reward_per_share = entry_price - target

        # R:R Calculation
        rr_ratio = reward_per_share / risk_per_share if risk_per_share > 0 else 0.0
        is_valid_rr = rr_ratio >= self.min_rr_ratio

        # Position Sizing Formula:
        # Risk Amount = Capital * Risk Percentage / 100
        # Position Size = Risk Amount / |Entry - Stop Loss|
        risk_budget = (capital * risk_pct) / 100.0

        raw_shares = risk_budget / risk_per_share if risk_per_share > 0 else 0
        # Integer lot size constraints (NSE Equity: 1 share lot)
        suggested_shares = int(math.floor(raw_shares / self.lot_size) * self.lot_size)
        suggested_shares = max(1, suggested_shares)

        # Cap position size so total capital required doesn't exceed available trading capital
        max_affordable_shares = int(capital // entry_price) if entry_price > 0 else 1
        suggested_shares = min(suggested_shares, max(1, max_affordable_shares))

        monetary_risk_actual = suggested_shares * risk_per_share
        potential_profit = suggested_shares * reward_per_share

        explanation = (
            f"Risk Calculation ({direction.upper()}): Entry ₹{entry_price:.2f}, Stop Loss ₹{stop_loss:.2f} "
            f"(risk/sh: ₹{risk_per_share:.2f}), Target ₹{target:.2f} (reward/sh: ₹{reward_per_share:.2f}). "
            f"R:R = 1:{rr_ratio:.2f}. "
            f"Suggested Size: {suggested_shares} shares for ₹{capital:,.0f} capital @ {risk_pct:.1f}% risk "
            f"(Total max monetary risk: ₹{monetary_risk_actual:.2f})."
        )

        return RiskProfile(
            entry_price=entry_price,
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            stop_loss=stop_loss,
            target=target,
            risk_reward_ratio=rr_ratio,
            risk_amount=risk_budget,
            suggested_shares=suggested_shares,
            monetary_risk_actual=monetary_risk_actual,
            potential_profit=potential_profit,
            trading_capital=capital,
            risk_percentage=risk_pct,
            is_valid_rr=is_valid_rr,
            explanation=explanation
        )

