'use client';

import React, { useState } from 'react';
import { runBacktest, uploadCsvBacktest, BacktestParams } from '../../services/api';
import { formatINR, formatPercent } from '../../utils/formatters';
import {
  Play,
  Upload,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Shield,
  Layers,
  CheckCircle2,
  XCircle,
  Clock,
  Coins,
  AlertTriangle,
} from 'lucide-react';

export const BacktestPanel: React.FC = () => {
  const [symbol, setSymbol] = useState<'HDFCBANK' | 'ICICIBANK'>('HDFCBANK');
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [riskPct, setRiskPct] = useState<number>(1.0);
  const [slippagePct, setSlippagePct] = useState<number>(0.05);
  const [minRR, setMinRR] = useState<number>(1.5);
  const [source, setSource] = useState<'synthetic' | 'database' | 'csv'>('synthetic');
  const [regime, setRegime] = useState<'bullish' | 'bearish' | 'sideways'>('bullish');
  const [csvContent, setCsvContent] = useState<string>('');
  const [csvFilename, setCsvFilename] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<any | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCsvFilename(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      setCsvContent(event.target?.result as string);
    };
    reader.readAsText(file);
  };

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      if (source === 'csv') {
        if (!csvContent) {
          throw new Error('Please select a valid CSV file with timestamp,open,high,low,close,volume.');
        }
        const res = await uploadCsvBacktest({
          symbol,
          csv_content: csvContent,
          initial_capital: initialCapital,
          risk_per_trade_pct: riskPct / 100.0,
          slippage_pct: slippagePct / 100.0,
        });
        setReport(res.data);
      } else {
        const params: BacktestParams = {
          symbol,
          initial_capital: initialCapital,
          risk_per_trade_pct: riskPct / 100.0,
          slippage_pct: slippagePct / 100.0,
          min_rr_ratio: minRR,
          source: source === 'database' ? 'database' : 'synthetic',
          synthetic_bars: 350,
          synthetic_regime: regime,
        };
        const res = await runBacktest(params);
        setReport(res.data);
      }
    } catch (e: any) {
      setError(e.message || 'Backtest failed to execute');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Configuration Header Card */}
      <div className="p-5 rounded-xl border border-terminal-border bg-terminal-card space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-terminal-border/60">
          <div>
            <h2 className="text-base font-mono font-bold text-white tracking-wide flex items-center gap-2">
              <BarChart3 className="text-terminal-accent" size={20} />
              HISTORICAL WALK-FORWARD BACKTESTING ENGINE
            </h2>
            <p className="text-xs font-mono text-slate-500 mt-0.5">
              Strictly zero look-ahead bias • Train/Val/Test Splits • Indian NSE statutory charges &amp; slippage simulation
            </p>
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={handleRun}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-terminal-accent hover:bg-terminal-accent/90 text-slate-900 font-mono font-bold text-xs transition-all shadow-md shadow-terminal-accent/20 disabled:opacity-50"
          >
            {loading ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} fill="currentColor" />}
            <span>{loading ? 'Simulating Historical Ticks...' : 'Run Walk-Forward Simulation'}</span>
          </button>
        </div>

        {/* Form Inputs Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-xs font-mono">
          <div>
            <label className="text-slate-500 uppercase text-[10px]">Instrument (Strict)</label>
            <div className="flex gap-1 mt-1">
              {(['HDFCBANK', 'ICICIBANK'] as const).map((sym) => (
                <button
                  key={sym}
                  type="button"
                  onClick={() => setSymbol(sym)}
                  className={`flex-1 py-1.5 rounded font-bold border transition-all ${
                    symbol === sym
                      ? 'bg-terminal-accent text-slate-900 border-terminal-accent'
                      : 'bg-terminal-bg text-slate-400 border-terminal-border hover:text-white'
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-slate-500 uppercase text-[10px]">Initial Capital (INR)</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full mt-1 px-3 py-1.5 bg-terminal-bg border border-terminal-border rounded text-slate-200 outline-none"
            />
          </div>

          <div>
            <label className="text-slate-500 uppercase text-[10px]">Risk per Trade (%)</label>
            <input
              type="number"
              step="0.1"
              value={riskPct}
              onChange={(e) => setRiskPct(Number(e.target.value))}
              className="w-full mt-1 px-3 py-1.5 bg-terminal-bg border border-terminal-border rounded text-slate-200 outline-none"
            />
          </div>

          <div>
            <label className="text-slate-500 uppercase text-[10px]">Execution Slippage (%)</label>
            <input
              type="number"
              step="0.01"
              value={slippagePct}
              onChange={(e) => setSlippagePct(Number(e.target.value))}
              className="w-full mt-1 px-3 py-1.5 bg-terminal-bg border border-terminal-border rounded text-slate-200 outline-none"
            />
          </div>

          <div>
            <label className="text-slate-500 uppercase text-[10px]">Data Source</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as any)}
              className="w-full mt-1 px-3 py-1.5 bg-terminal-bg border border-terminal-border rounded text-slate-200 outline-none"
            >
              <option value="synthetic">Synthetic Walk-Forward</option>
              <option value="database">Database Live Candles</option>
              <option value="csv">Custom CSV Upload</option>
            </select>
          </div>

          {source === 'synthetic' && (
            <div>
              <label className="text-slate-500 uppercase text-[10px]">Simulated Market Regime</label>
              <select
                value={regime}
                onChange={(e) => setRegime(e.target.value as any)}
                className="w-full mt-1 px-3 py-1.5 bg-terminal-bg border border-terminal-border rounded text-slate-200 outline-none"
              >
                <option value="bullish">Trending Bullish</option>
                <option value="bearish">Trending Bearish</option>
                <option value="sideways">Sideways Consolidation</option>
              </select>
            </div>
          )}

          {source === 'csv' && (
            <div className="col-span-2">
              <label className="text-slate-500 uppercase text-[10px]">Upload Historical 1m CSV</label>
              <div className="flex items-center gap-2 mt-1">
                <label className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-slate-300">
                  <Upload size={14} />
                  <span>Choose CSV</span>
                  <input type="file" accept=".csv" onChange={handleFileUpload} className="hidden" />
                </label>
                <span className="text-[11px] text-slate-400 truncate max-w-[200px]">
                  {csvFilename || 'No file selected'}
                </span>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Backtest Results Area */}
      {report && (
        <div className="space-y-6">
          {/* Top KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Net Profit (Post Fees)</span>
              <div
                className={`text-xl font-bold font-mono mt-1 ${
                  report.net_profit >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {report.net_profit >= 0 ? '+' : ''}
                {formatINR(report.net_profit)}
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                Return: {report.return_pct}%
              </span>
            </div>

            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Win Rate</span>
              <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
                {report.win_rate}%
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                {report.winning_trades}W / {report.losing_trades}L of {report.total_trades} trades
              </span>
            </div>

            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Profit Factor</span>
              <div className="text-xl font-bold font-mono text-white mt-1">
                {report.profit_factor}
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                Gross Win/Loss Ratio
              </span>
            </div>

            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Max Drawdown</span>
              <div className="text-xl font-bold font-mono text-rose-400 mt-1">
                {report.max_drawdown_pct}%
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                -{formatINR(report.max_drawdown)}
              </span>
            </div>

            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Expectancy / Trade</span>
              <div
                className={`text-xl font-bold font-mono mt-1 ${
                  report.expectancy >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {report.expectancy >= 0 ? '+' : ''}
                {formatINR(report.expectancy)}
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                Avg Hold: {report.avg_holding_time_minutes}m
              </span>
            </div>

            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card">
              <span className="text-[10px] font-mono text-slate-500 uppercase">NSE Charges Paid</span>
              <div className="text-xl font-bold font-mono text-amber-400 mt-1">
                {formatINR(report.total_charges)}
              </div>
              <span className="text-[10px] font-mono text-slate-500">
                Brokerage + STT + GST
              </span>
            </div>
          </div>

          {/* Walk-Forward Splits & Market Regimes Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Walk Forward Splits */}
            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card space-y-3">
              <div className="flex items-center gap-2 pb-2 border-b border-terminal-border/60">
                <Layers size={16} className="text-terminal-accent" />
                <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                  Walk-Forward Split Breakdown (No Look-Ahead)
                </h3>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                {['train', 'validation', 'test'].map((sKey) => {
                  const s = report.splits?.[sKey] || {};
                  const isTest = sKey === 'test';
                  return (
                    <div
                      key={sKey}
                      className={`p-3 rounded-lg border ${
                        isTest
                          ? 'bg-sky-950/20 border-sky-500/30'
                          : 'bg-terminal-bg border-terminal-border'
                      }`}
                    >
                      <span className="text-[10px] uppercase font-bold text-slate-400">
                        {sKey === 'test' ? 'Out-of-Sample' : sKey}
                      </span>
                      <div className="text-sm font-bold text-white mt-1">
                        {s.trades || 0} Trades
                      </div>
                      <div className="text-xs text-emerald-400 mt-0.5">
                        Win Rate: {s.win_rate ?? 0}%
                      </div>
                      <div
                        className={`text-xs font-semibold mt-0.5 ${
                          (s.net_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {formatINR(s.net_pnl || 0)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Market Regimes */}
            <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card space-y-3">
              <div className="flex items-center gap-2 pb-2 border-b border-terminal-border/60">
                <Shield size={16} className="text-terminal-accent" />
                <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                  Performance by Market Regime
                </h3>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {Object.entries(report.regimes || {}).map(([rKey, val]: [string, any]) => (
                  <div key={rKey} className="p-2.5 rounded-lg bg-terminal-bg border border-terminal-border">
                    <div className="text-[10px] uppercase text-slate-400 truncate">
                      {rKey.replace('_', ' ')}
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <span className="text-white font-bold">{val.trades} Trades</span>
                      <span
                        className={`font-semibold ${
                          val.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {formatINR(val.net_pnl)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Trade-by-Trade Table */}
          <div className="rounded-xl border border-terminal-border bg-terminal-card overflow-hidden">
            <div className="p-4 border-b border-terminal-border/60 flex items-center justify-between">
              <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider">
                Simulated Execution Log ({report.trades?.length || 0} Trades)
              </h3>
              <span className="text-[11px] font-mono text-slate-500">
                Signal Rules Identical to Step 2 Engine
              </span>
            </div>

            <div className="overflow-x-auto max-h-[400px]">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-900/60 text-slate-400 uppercase text-[10px] tracking-wider sticky top-0 border-b border-terminal-border">
                  <tr>
                    <th className="p-3">#</th>
                    <th className="p-3">Entry Time</th>
                    <th className="p-3">Side</th>
                    <th className="p-3">Entry Price</th>
                    <th className="p-3">Exit Price</th>
                    <th className="p-3">Exit Reason</th>
                    <th className="p-3">NSE Charges</th>
                    <th className="p-3">Net P&amp;L</th>
                    <th className="p-3">Split</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border/40">
                  {(report.trades || []).map((t: any, idx: number) => {
                    const isBuy = t.side === 'BUY';
                    return (
                      <tr key={t.trade_id || idx} className="hover:bg-slate-800/20">
                        <td className="p-3 text-slate-500">{idx + 1}</td>
                        <td className="p-3 text-slate-300 whitespace-nowrap">{t.entry_time}</td>
                        <td className="p-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              isBuy
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            {t.side}
                          </span>
                        </td>
                        <td className="p-3 text-slate-200">{formatINR(t.entry_price)}</td>
                        <td className="p-3 text-slate-200">{formatINR(t.exit_price)}</td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] border ${
                              t.exit_reason === 'HIT_TARGET'
                                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                                : t.exit_reason === 'HIT_STOP_LOSS'
                                ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
                                : 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                            }`}
                          >
                            {t.exit_reason}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400">{formatINR(t.charges)}</td>
                        <td className="p-3">
                          <span
                            className={`font-bold ${
                              t.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {t.net_pnl >= 0 ? '+' : ''}
                            {formatINR(t.net_pnl)}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400">{t.split}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

