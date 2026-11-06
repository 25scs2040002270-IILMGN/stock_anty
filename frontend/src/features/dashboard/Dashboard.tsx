'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { MarketTick, Candle, ConnectionStatus, ConnectionLog, SignalResponse } from '../../types/market';
import { PriceCard } from '../../components/PriceCard';
import { CandleChart } from '../charts/CandleChart';
import { StatusBadge } from '../../components/StatusBadge';
import { SignalCard } from '../signals/SignalCard';
import { fetchConnectionLogs, fetchAnalysis } from '../../services/api';
import { notifications } from '../../utils/notifications';
import { Layers, Activity, RefreshCw, Terminal, CheckCircle2, Zap } from 'lucide-react';

interface Props {
  ticks: Record<string, MarketTick>;
  activeCandles: Record<string, Candle>;
  connectionStatus: ConnectionStatus | null;
  onRefresh: () => void;
}

export const Dashboard: React.FC<Props> = ({
  ticks,
  activeCandles,
  connectionStatus,
  onRefresh,
}) => {
  const [selectedSymbol, setSelectedSymbol] = useState<'HDFCBANK' | 'ICICIBANK'>('HDFCBANK');
  const [signal, setSignal] = useState<SignalResponse | null>(null);
  const [loadingSignal, setLoadingSignal] = useState<boolean>(false);
  const [logs, setLogs] = useState<ConnectionLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState<boolean>(false);
  const lastAlertKeyRef = React.useRef<string>('');

  const loadSignal = useCallback(async () => {
    setLoadingSignal(true);
    try {
      const data = await fetchAnalysis(selectedSymbol);
      setSignal(data);

      if (data && (data.direction === 'BUY' || data.direction === 'SELL')) {
        const key = `${selectedSymbol}_${data.direction}_${data.signal_timestamp}`;
        if (lastAlertKeyRef.current !== key) {
          lastAlertKeyRef.current = key;
          notifications.playSignalChime(data.direction === 'BUY');
          notifications.notifySignal(
            selectedSymbol,
            data.direction,
            data.current_market_price,
            data.scoring_breakdown?.total_score || 0
          );
        }
      }
    } catch (e) {
      // offline / waiting
    } finally {
      setLoadingSignal(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    loadSignal();
    const interval = setInterval(loadSignal, 20000);
    return () => clearInterval(interval);
  }, [loadSignal]);

  const loadLogs = async () => {
    setLoadingLogs(true);
    try {
      const data = await fetchConnectionLogs(20);
      setLogs(data);
    } catch (e) {
      // offline
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    loadLogs();
    const interval = setInterval(loadLogs, 15000);
    return () => clearInterval(interval);
  }, []);

  const activeCandle = activeCandles[`${selectedSymbol}_1m`] || null;

  return (
    <div className="space-y-6">
      {/* Top Banner: Connection & Provider Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Provider Status */}
        <div className="p-4 rounded-xl bg-terminal-card border border-terminal-border flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-500 block">Feed Provider</span>
            <span className="text-sm font-bold font-mono text-slate-200">
              {connectionStatus?.provider || 'UPSTOX V3'}
            </span>
          </div>
          <StatusBadge state={connectionStatus?.state || 'DISCONNECTED'} />
        </div>

        {/* Subscriptions */}
        <div className="p-4 rounded-xl bg-terminal-card border border-terminal-border">
          <span className="text-[11px] font-mono text-slate-500 block">Active Subscriptions</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-base font-bold font-mono text-emerald-400">
              {connectionStatus?.subscription_count || 2} Instruments
            </span>
            <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
              HDFCBANK, ICICIBANK
            </span>
          </div>
        </div>

        {/* Feed Freshness */}
        <div className="p-4 rounded-xl bg-terminal-card border border-terminal-border">
          <span className="text-[11px] font-mono text-slate-500 block">Tick Freshness</span>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm font-bold font-mono text-slate-200">
              {connectionStatus?.last_tick_time_sec_ago !== null && connectionStatus?.last_tick_time_sec_ago !== undefined
                ? `${connectionStatus.last_tick_time_sec_ago}s ago`
                : 'Awaiting ticks'}
            </span>
          </div>
        </div>

        {/* Socket Health */}
        <div className="p-4 rounded-xl bg-terminal-card border border-terminal-border">
          <span className="text-[11px] font-mono text-slate-500 block">Socket State</span>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                connectionStatus?.is_socket_connected ? 'bg-emerald-400' : 'bg-rose-500'
              }`}
            />
            <span className="text-sm font-bold font-mono text-slate-200">
              {connectionStatus?.is_socket_connected ? 'WebSocket Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Stock Cards: HDFCBANK & ICICIBANK */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-2">
            <Layers size={14} className="text-terminal-accent" />
            Configured Equities (Click card to select & analyse)
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            Official Upstox Protobuf Normalized Feed
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PriceCard
            symbol="HDFCBANK"
            instrumentKey="NSE_EQ|INE040A01034"
            name="HDFC Bank Limited"
            tick={ticks['HDFCBANK'] || null}
            isSelected={selectedSymbol === 'HDFCBANK'}
            onSelect={() => setSelectedSymbol('HDFCBANK')}
          />
          <PriceCard
            symbol="ICICIBANK"
            instrumentKey="NSE_EQ|INE090A01021"
            name="ICICI Bank Limited"
            tick={ticks['ICICIBANK'] || null}
            isSelected={selectedSymbol === 'ICICIBANK'}
            onSelect={() => setSelectedSymbol('ICICIBANK')}
          />
        </div>
      </div>

      {/* Real-Time Quantitative Signal Engine Output */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold flex items-center gap-1.5">
            <Zap size={14} className="text-amber-400" />
            Quantitative Signal Engine ({selectedSymbol})
          </h3>
          <button
            type="button"
            onClick={loadSignal}
            disabled={loadingSignal}
            className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-slate-200"
          >
            <RefreshCw size={11} className={loadingSignal ? 'animate-spin' : ''} />
            <span>Re-evaluate</span>
          </button>
        </div>
        <SignalCard signal={signal} loading={loadingSignal} onRefresh={loadSignal} />
      </div>

      {/* Chart Section */}
      <div className="h-[480px]">
        <CandleChart symbol={selectedSymbol} activeCandle={activeCandle} />
      </div>

      {/* Connection & Audit Logs Panel */}
      <div className="rounded-xl border border-terminal-border bg-terminal-card p-4">
        <div className="flex items-center justify-between pb-3 border-b border-terminal-border/60">
          <div className="flex items-center gap-2">
            <Terminal size={16} className="text-terminal-accent" />
            <h3 className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wide">
              Connection & Feed Audit Logs (SQLite)
            </h3>
          </div>
          <button
            type="button"
            onClick={loadLogs}
            disabled={loadingLogs}
            className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 hover:text-slate-200"
          >
            <RefreshCw size={12} className={loadingLogs ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        <div className="mt-3 overflow-x-auto max-h-48 overflow-y-auto">
          {logs.length === 0 ? (
            <div className="py-6 text-center text-xs font-mono text-slate-500">
              No connection logs recorded yet.
            </div>
          ) : (
            <table className="w-full text-left font-mono text-[11px]">
              <thead>
                <tr className="text-slate-500 border-b border-terminal-border/40 pb-1">
                  <th className="pb-1.5">Timestamp (IST)</th>
                  <th className="pb-1.5">Provider</th>
                  <th className="pb-1.5">State</th>
                  <th className="pb-1.5">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border/20">
                {logs.map((log) => (
                  <tr key={log.id} className="text-slate-300">
                    <td className="py-1 text-slate-500 whitespace-nowrap">{log.timestamp}</td>
                    <td className="py-1 text-slate-400">{log.provider}</td>
                    <td className="py-1">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          log.state === 'LIVE'
                            ? 'bg-emerald-950 text-emerald-400'
                            : log.state === 'STALE'
                            ? 'bg-yellow-950 text-yellow-400'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {log.state}
                      </span>
                    </td>
                    <td className="py-1 text-slate-300 truncate max-w-md">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
