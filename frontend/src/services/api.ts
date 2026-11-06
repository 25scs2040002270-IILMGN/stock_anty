import {
  HealthStatus,
  ConnectionStatus,
  InstrumentInfo,
  Candle,
  ConnectionLog,
  SignalResponse,
  RiskSettings
} from '../types/market';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE_URL}/api/health`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchMarketStatus(): Promise<ConnectionStatus> {
  const res = await fetch(`${API_BASE_URL}/api/market/status`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Market status failed: ${res.statusText}`);
  return res.json();
}

export async function fetchInstruments(): Promise<InstrumentInfo[]> {
  const res = await fetch(`${API_BASE_URL}/api/market/instruments`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Instruments fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchLatestTicks(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE_URL}/api/market/latest`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Latest ticks fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchCandles(symbol: string, timeframe: '1m' | '5m' | '15m' = '1m', limit: number = 100): Promise<Candle[]> {
  const res = await fetch(`${API_BASE_URL}/api/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Candles fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchConnectionLogs(limit: number = 50): Promise<ConnectionLog[]> {
  const res = await fetch(`${API_BASE_URL}/api/market/logs?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Logs fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchAuthStatus(): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/auth/status`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Auth status fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchLoginUrl(): Promise<{ authorization_url: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login-url`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Login URL fetch failed: ${res.statusText}`);
  return res.json();
}

export async function submitManualToken(token: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error(`Token update failed: ${res.statusText}`);
  return res.json();
}

// ----------------------------------------------------
// Step 2 Technical Analysis & Signal APIs
// ----------------------------------------------------
export async function fetchAnalysis(symbol: 'HDFCBANK' | 'ICICIBANK'): Promise<SignalResponse> {
  const res = await fetch(`${API_BASE_URL}/api/analysis/${symbol}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Analysis fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchActiveSignals(symbol?: string): Promise<any[]> {
  const url = symbol ? `${API_BASE_URL}/api/signals?symbol=${symbol}` : `${API_BASE_URL}/api/signals`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Active signals fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchSignalsHistory(symbol?: string, limit: number = 50): Promise<any[]> {
  const url = symbol
    ? `${API_BASE_URL}/api/signals/history?symbol=${symbol}&limit=${limit}`
    : `${API_BASE_URL}/api/signals/history?limit=${limit}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Signals history fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchIndicators(symbol: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/indicators/${symbol}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Indicators fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchRiskSettings(): Promise<RiskSettings> {
  const res = await fetch(`${API_BASE_URL}/api/risk/settings`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Risk settings fetch failed: ${res.statusText}`);
  return res.json();
}

export async function updateRiskSettings(settings: Partial<RiskSettings>): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/risk/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error(`Risk settings update failed: ${res.statusText}`);
  return res.json();
}

// ----------------------------------------------------
// Step 3 Backtesting & Evaluated Signals APIs
// ----------------------------------------------------
export interface BacktestParams {
  symbol: 'HDFCBANK' | 'ICICIBANK';
  initial_capital?: number;
  risk_per_trade_pct?: number;
  slippage_pct?: number;
  min_rr_ratio?: number;
  source?: 'synthetic' | 'database';
  synthetic_bars?: number;
  synthetic_regime?: 'bullish' | 'bearish' | 'sideways';
}

export async function runBacktest(params: BacktestParams): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Backtest failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchRecentBacktests(limit: number = 10): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/api/backtest/recent?limit=${limit}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Recent backtests fetch failed: ${res.statusText}`);
  const data = await res.json();
  return data.data || [];
}

export async function fetchBacktestResult(id: number): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/backtest/results/${id}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Backtest report fetch failed: ${res.statusText}`);
  const data = await res.json();
  return data.data;
}

export async function uploadCsvBacktest(params: {
  symbol: 'HDFCBANK' | 'ICICIBANK';
  csv_content: string;
  initial_capital?: number;
  risk_per_trade_pct?: number;
  slippage_pct?: number;
}): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/backtest/upload-csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `CSV backtest failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchDailyRiskSummary(): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/signals/daily-summary`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Daily risk summary failed: ${res.statusText}`);
  const data = await res.json();
  return data.data;
}

export async function fetchEvaluatedSignalsHistory(symbol?: string, limit: number = 50): Promise<any[]> {
  const url = symbol
    ? `${API_BASE_URL}/api/signals/evaluated-history?symbol=${symbol}&limit=${limit}`
    : `${API_BASE_URL}/api/signals/evaluated-history?limit=${limit}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Evaluated signals fetch failed: ${res.statusText}`);
  const data = await res.json();
  return data.data || [];
}
