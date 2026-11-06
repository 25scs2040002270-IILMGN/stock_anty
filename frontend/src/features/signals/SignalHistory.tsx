'use client';

import React, { useEffect, useState } from 'react';
import { fetchEvaluatedSignalsHistory } from '../../services/api';
import { formatINR } from '../../utils/formatters';
import {
  TrendingUp,
  TrendingDown,
  PauseCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  AlertOctagon,
  Filter,
} from 'lucide-react';

export const SignalHistory: React.FC = () => {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterSymbol, setFilterSymbol] = useState<string>('ALL');
  const [filterOutcome, setFilterOutcome] = useState<string>('ALL');

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await fetchEvaluatedSignalsHistory(
        filterSymbol === 'ALL' ? undefined : filterSymbol,
        100
      );
      setHistory(data || []);
    } catch (e) {
      console.error('Failed to load evaluated signals:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [filterSymbol]);

  const filtered = history.filter((item) => {
    if (filterOutcome === 'ALL') return true;
    const outcome = item.outcome || 'ACTIVE';
    return outcome.toUpperCase() === filterOutcome.toUpperCase();
  });

  // Calculate summary metrics
  const completedTrades = filtered.filter(
    (item) => item.outcome === 'HIT_TARGET' || item.outcome === 'HIT_STOP_LOSS'
  );
  const targetHits = filtered.filter((item) => item.outcome === 'HIT_TARGET').length;
  const stopHits = filtered.filter((item) => item.outcome === 'HIT_STOP_LOSS').length;
  const winRate =
    completedTrades.length > 0
      ? ((targetHits / completedTrades.length) * 100).toFixed(1)
      : '0.0';

  const totalNetPnl = filtered.reduce((acc, curr) => acc + (curr.pnl_net || 0), 0);

  return (
    <div className="space-y-4">
      {/* Top Controls & Metrics Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono text-slate-500 uppercase">Total Signals</span>
            <div className="text-xl font-bold font-mono text-white">{filtered.length}</div>
          </div>
          <Clock size={20} className="text-terminal-accent" />
        </div>

        <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono text-slate-500 uppercase">Completed Win Rate</span>
            <div className="text-xl font-bold font-mono text-emerald-400">
              {winRate}%
              <span className="text-xs text-slate-500 ml-1">
                ({targetHits}W / {stopHits}L)
              </span>
            </div>
          </div>
          <CheckCircle2 size={20} className="text-emerald-400" />
        </div>

        <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono text-slate-500 uppercase">Evaluated Net P&amp;L</span>
            <div
              className={`text-xl font-bold font-mono ${
                totalNetPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {totalNetPnl >= 0 ? '+' : ''}
              {formatINR(totalNetPnl)}
            </div>
          </div>
          <AlertOctagon size={20} className={totalNetPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'} />
        </div>

        <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-[10px] font-mono text-slate-500 uppercase">Filter Stocks</span>
            <div className="flex gap-1 mt-1">
              {(['ALL', 'HDFCBANK', 'ICICIBANK'] as const).map((sym) => (
                <button
                  key={sym}
                  type="button"
                  onClick={() => setFilterSymbol(sym)}
                  className={`px-2 py-0.5 text-[11px] font-mono rounded ${
                    filterSymbol === sym
                      ? 'bg-terminal-accent text-slate-900 font-bold'
                      : 'text-slate-400 hover:text-white bg-slate-800'
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={loadHistory}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all"
            title="Refresh history"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* History Table Container */}
      <div className="rounded-xl border border-terminal-border bg-terminal-card overflow-hidden">
        <div className="p-4 border-b border-terminal-border/60 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 className="font-mono text-sm font-bold text-white uppercase tracking-wider">
              Objective Signal Outcomes Log
            </h3>
            <span className="text-xs font-mono text-slate-500">
              (Analytical Suggestions evaluated against subsequent candle price action)
            </span>
          </div>

          {/* Outcome Filter */}
          <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
            <Filter size={14} />
            <span>Outcome:</span>
            <select
              value={filterOutcome}
              onChange={(e) => setFilterOutcome(e.target.value)}
              className="bg-terminal-bg border border-terminal-border rounded px-2 py-1 text-xs font-mono text-slate-200 outline-none"
            >
              <option value="ALL">All Outcomes</option>
              <option value="HIT_TARGET">Target Hit</option>
              <option value="HIT_STOP_LOSS">Stop Loss Hit</option>
              <option value="EXPIRED">Expired (15m)</option>
              <option value="ACTIVE">Active</option>
              <option value="INVALIDATED">Invalidated</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center text-xs font-mono text-slate-500 animate-pulse">
            Loading evaluated signal decisions from SQLite database...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-xs font-mono text-slate-500">
            No historical signals recorded yet. Signals log automatically as completed candles finalize.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-terminal-border">
                <tr>
                  <th className="p-3">Time (IST)</th>
                  <th className="p-3">Symbol</th>
                  <th className="p-3">Direction</th>
                  <th className="p-3">Score</th>
                  <th className="p-3">Entry</th>
                  <th className="p-3">Stop Loss</th>
                  <th className="p-3">Target</th>
                  <th className="p-3">Outcome</th>
                  <th className="p-3">Exit Price</th>
                  <th className="p-3">Net P&amp;L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border/40">
                {filtered.map((sig, idx) => {
                  const isBuy = sig.direction === 'BUY';
                  const isSell = sig.direction === 'SELL';
                  const outcome = sig.outcome || sig.status || 'ACTIVE';

                  let outcomeBadgeClass = 'bg-slate-800 text-slate-400 border-slate-700';
                  if (outcome === 'HIT_TARGET') {
                    outcomeBadgeClass = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
                  } else if (outcome === 'HIT_STOP_LOSS') {
                    outcomeBadgeClass = 'bg-rose-500/20 text-rose-400 border-rose-500/40';
                  } else if (outcome === 'EXPIRED') {
                    outcomeBadgeClass = 'bg-amber-500/20 text-amber-400 border-amber-500/40';
                  } else if (outcome === 'ACTIVE') {
                    outcomeBadgeClass = 'bg-sky-500/20 text-sky-400 border-sky-500/40';
                  }

                  return (
                    <tr key={sig.id || idx} className="hover:bg-slate-800/20 transition-colors">
                      <td className="p-3 text-slate-300 whitespace-nowrap">
                        {sig.signal_datetime_ist || sig.signal_timestamp}
                      </td>
                      <td className="p-3 font-bold text-white">{sig.symbol}</td>
                      <td className="p-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                            isBuy
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : isSell
                              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                              : 'bg-slate-800 text-amber-400 border border-slate-700'
                          }`}
                        >
                          {isBuy ? <TrendingUp size={10} /> : isSell ? <TrendingDown size={10} /> : <PauseCircle size={10} />}
                          {sig.direction}
                        </span>
                      </td>
                      <td className="p-3 text-slate-400">{sig.score ?? sig.technical_score ?? 'N/A'}/100</td>
                      <td className="p-3 text-slate-200">
                        {sig.entry_price ? formatINR(sig.entry_price) : formatINR(sig.current_market_price)}
                      </td>
                      <td className="p-3 text-rose-400">
                        {sig.stop_loss ? formatINR(sig.stop_loss) : '-'}
                      </td>
                      <td className="p-3 text-emerald-400">
                        {sig.target ? formatINR(sig.target) : '-'}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 text-[10px] font-semibold rounded border ${outcomeBadgeClass}`}
                        >
                          {outcome}
                        </span>
                      </td>
                      <td className="p-3 text-slate-300">
                        {sig.exit_price ? formatINR(sig.exit_price) : '-'}
                      </td>
                      <td className="p-3">
                        {sig.pnl_net !== null && sig.pnl_net !== undefined ? (
                          <span
                            className={`font-bold ${
                              sig.pnl_net >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {sig.pnl_net >= 0 ? '+' : ''}
                            {formatINR(sig.pnl_net)}
                          </span>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

