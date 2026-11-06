from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


@dataclass
class InstrumentRecord:
    instrument_key: str
    trading_symbol: str
    exchange: str
    segment: str
    instrument_type: str
    tick_size: float = 0.05
    lot_size: int = 1
    is_active: bool = True
    resolved_at: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandleRecord:
    instrument_key: str
    symbol: str
    timeframe: str  # '1m', '5m', '15m'
    open_time: int  # Epoch seconds start of candle
    close_time: int  # Epoch seconds end of candle
    open_datetime_ist: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    is_complete: bool = False
    id: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectionLogRecord:
    provider: str
    state: str  # LIVE, DELAYED, STALE, DISCONNECTED
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: int = 0
    datetime_ist: str = ""
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SignalRecord:
    symbol: str
    direction: str  # 'BUY', 'SELL', 'WAIT'
    signal_timestamp: int
    signal_datetime_ist: str
    current_market_price: float
    entry_price: Optional[float]
    entry_zone_low: Optional[float]
    entry_zone_high: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    risk_reward_ratio: Optional[float]
    score: int
    status: str = "ACTIVE"  # 'ACTIVE', 'EXPIRED', 'INVALIDATED'
    invalidation_reason: Optional[str] = None
    outcome: Optional[str] = "ACTIVE"  # 'ACTIVE', 'HIT_TARGET', 'HIT_STOP_LOSS', 'EXPIRED', 'INVALIDATED'
    exit_price: Optional[float] = None
    exit_timestamp: Optional[int] = None
    pnl_gross: Optional[float] = None
    pnl_net: Optional[float] = None
    payload: Optional[Dict[str, Any]] = None
    id: Optional[int] = None
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskSettings:
    trading_capital: float = 100000.0  # ₹1,00,000 INR default personal capital
    risk_percentage: float = 1.0       # 1.0% risk per trade default
    max_risk_reward_min: float = 1.5   # Minimum 1:1.5 R:R required
    lot_size: int = 1                  # NSE equity lot size = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TradeRecord:
    symbol: str
    direction: str  # 'BUY', 'SELL'
    entry_time: int
    entry_datetime_ist: str
    entry_price: float
    exit_time: int
    exit_datetime_ist: str
    exit_price: float
    shares: int
    stop_loss: float
    target: float
    exit_reason: str  # 'TARGET_HIT', 'STOP_LOSS_HIT', 'TIME_EXPIRED', 'INVALIDATED'
    gross_pnl: float
    brokerage_and_taxes: float
    net_pnl: float
    pnl_percent: float
    holding_time_minutes: int
    market_condition: str  # 'TRENDING', 'SIDEWAYS', 'VOLATILE'
    sample_split: str  # 'TRAIN', 'VALIDATION', 'TEST'
    score_at_entry: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BacktestRunRecord:
    id: Optional[int]
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_signals: int
    buy_signals: int
    sell_signals: int
    wait_signals: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    gross_pnl: float
    net_pnl: float
    total_charges: float
    avg_holding_time_minutes: float
    summary: Dict[str, Any]
    train_metrics: Dict[str, Any]
    validation_metrics: Dict[str, Any]
    test_metrics: Dict[str, Any]
    market_conditions_breakdown: Dict[str, Any]
    trades: List[Dict[str, Any]]
    created_at: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
