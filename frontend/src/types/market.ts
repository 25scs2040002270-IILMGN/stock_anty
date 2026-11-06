export type ConnectionState = 'LIVE' | 'DELAYED' | 'STALE' | 'DISCONNECTED';

export interface DepthLevel {
  quantity: number;
  price: number;
  orders?: number;
}

export interface OHLCData {
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface MarketTick {
  symbol: string;
  instrument_key: string;
  exchange: string;
  ltp: number;
  exchange_timestamp: number; // epoch ms
  last_traded_quantity: number;
  cumulative_volume: number;
  ohlc?: OHLCData | null;
  bids: DepthLevel[];
  asks: DepthLevel[];
  received_at: number; // epoch ms
  provider: string;
  data_status: string;
}

export interface Candle {
  symbol: string;
  timeframe: '1m' | '5m' | '15m';
  open_time: number; // epoch seconds
  close_time: number; // epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_complete: boolean;
  received_at?: number;
}

export interface ConnectionStatus {
  provider: string;
  state: ConnectionState;
  is_socket_connected: boolean;
  subscribed_instruments: string[];
  subscription_count: number;
  reconnect_count: number;
  last_tick_time_sec_ago: number | null;
  last_exchange_datetime_ist: string | null;
  is_market_session_open: boolean;
  evaluated_at: string;
}

export interface InstrumentInfo {
  trading_symbol: string;
  instrument_key: string;
  exchange: string;
  instrument_type: string;
  name?: string;
  lot_size?: number;
  is_active: boolean;
}

export interface HealthStatus {
  status: string;
  app_env: string;
  market_open: boolean;
  current_time_ist: string;
  supported_instruments: string[];
  forbidden_instruments_enforced: boolean;
}

export interface ConnectionLog {
  id: number;
  timestamp: string;
  provider: string;
  state: string;
  message: string;
  details?: Record<string, any>;
}

export interface WSMessage {
  type: 'tick' | 'candle' | 'status' | 'signal' | 'error';
  data: any;
  timestamp?: number;
}

// ----------------------------------------------------
// Step 2 Technical Analysis & Signal Types
// ----------------------------------------------------
export interface ScoreBreakdown {
  total_score: number;
  max_score: number;
  trend_15m_score: number;
  setup_5m_score: number;
  entry_1m_score: number;
  ema_score: number;
  vwap_score: number;
  rsi_score: number;
  volume_score: number;
  structure_score: number;
  sr_score: number;
  candlestick_score: number;
  liquidity_penalty: number;
  notes: string[];
}

export interface PositionSizing {
  entry_price: number;
  entry_zone: { low: number; high: number };
  stop_loss: number;
  target: number;
  risk_reward_ratio: number;
  risk_amount_budget: number;
  suggested_shares: number;
  monetary_risk_actual: number;
  potential_profit: number;
  trading_capital: number;
  risk_percentage: number;
  is_valid_rr: boolean;
  explanation: string;
}

export interface SignalResponse {
  symbol: string;
  direction: 'BUY' | 'SELL' | 'WAIT';
  signal_timestamp: number;
  signal_datetime_ist: string;
  current_market_price: number;
  entry_zone: { low: number; center: number; high: number };
  stop_loss: number;
  target: number;
  risk_reward_ratio: number;
  expected_validity_minutes: number;
  scoring_breakdown: ScoreBreakdown;
  trend_15m_explanation: string;
  setup_5m_explanation: string;
  entry_1m_explanation: string;
  ema_explanation: string;
  rsi_explanation: string;
  vwap_explanation: string;
  volume_confirmation: string;
  support_resistance_explanation: string;
  candlestick_confirmation: string;
  liquidity_sweep_risk: string;
  invalidation_condition: string;
  data_freshness_status: string;
  position_sizing?: PositionSizing | null;
  id?: number | null;
}

export interface RiskSettings {
  trading_capital: number;
  risk_percentage: number;
  max_risk_reward_min: number;
  lot_size: number;
}
