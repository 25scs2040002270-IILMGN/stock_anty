from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List


@dataclass
class ScoreBreakdown:
    total_score: int
    max_score: int
    trend_15m_score: int
    setup_5m_score: int
    entry_1m_score: int
    ema_score: int
    vwap_score: int
    rsi_score: int
    volume_score: int
    structure_score: int
    sr_score: int
    candlestick_score: int
    liquidity_penalty: int
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SignalResponse:
    symbol: str
    direction: str                      # 'BUY', 'SELL', 'WAIT'
    signal_timestamp: int               # Epoch seconds
    signal_datetime_ist: str
    current_market_price: float
    entry_zone: Dict[str, float]        # {'low': ..., 'center': ..., 'high': ...}
    stop_loss: float
    target: float
    risk_reward_ratio: float
    expected_validity_minutes: int
    scoring_breakdown: ScoreBreakdown
    trend_15m_explanation: str
    setup_5m_explanation: str
    entry_1m_explanation: str
    ema_explanation: str
    rsi_explanation: str
    vwap_explanation: str
    volume_confirmation: str
    support_resistance_explanation: str
    candlestick_confirmation: str
    liquidity_sweep_risk: str
    invalidation_condition: str
    data_freshness_status: str          # 'LIVE', 'DELAYED', 'STALE', 'DISCONNECTED'
    position_sizing: Optional[Dict[str, Any]] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "signal_timestamp": self.signal_timestamp,
            "signal_datetime_ist": self.signal_datetime_ist,
            "current_market_price": round(self.current_market_price, 2),
            "entry_zone": self.entry_zone,
            "stop_loss": round(self.stop_loss, 2),
            "target": round(self.target, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "expected_validity_minutes": self.expected_validity_minutes,
            "scoring_breakdown": self.scoring_breakdown.to_dict(),
            "trend_15m_explanation": self.trend_15m_explanation,
            "setup_5m_explanation": self.setup_5m_explanation,
            "entry_1m_explanation": self.entry_1m_explanation,
            "ema_explanation": self.ema_explanation,
            "rsi_explanation": self.rsi_explanation,
            "vwap_explanation": self.vwap_explanation,
            "volume_confirmation": self.volume_confirmation,
            "support_resistance_explanation": self.support_resistance_explanation,
            "candlestick_confirmation": self.candlestick_confirmation,
            "liquidity_sweep_risk": self.liquidity_sweep_risk,
            "invalidation_condition": self.invalidation_condition,
            "data_freshness_status": self.data_freshness_status,
            "position_sizing": self.position_sizing,
            "id": self.id
        }

