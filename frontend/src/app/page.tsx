'use client';

import React, { useState } from 'react';
import { useMarketFeed } from '../hooks/useMarketFeed';
import { Header } from '../components/Header';
import { Sidebar, NavTab } from '../components/Sidebar';
import { Dashboard } from '../features/dashboard/Dashboard';
import { CandleChart } from '../features/charts/CandleChart';
import { SignalHistory } from '../features/signals/SignalHistory';
import { BacktestPanel } from '../features/backtesting/BacktestPanel';
import { SettingsPanel } from '../features/settings/Settings';
import { fetchConnectionLogs } from '../services/api';
import { ConnectionLog } from '../types/market';
import { RefreshCw, Terminal } from 'lucide-react';

export default function Home() {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [chartSymbol, setChartSymbol] = useState<'HDFCBANK' | 'ICICIBANK'>('HDFCBANK');
  const [logs, setLogs] = useState<ConnectionLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState<boolean>(false);

  const {
    ticks,
    activeCandles,
    connectionStatus,
    health,
    isWsConnected,
    refreshStatus,
  } = useMarketFeed();

  const loadLogs = async () => {
    setLoadingLogs(true);
    try {
      const data = await fetchConnectionLogs(100);
      setLogs(data);
    } catch (e) {
      // offline
    } finally {
      setLoadingLogs(false);
    }
  };

  const activeCandle = activeCandles[`${chartSymbol}_1m`] || null;

  return (
    <div className="flex flex-col min-h-screen bg-terminal-bg text-terminal-text">
      {/* Top Header */}
      <Header
        status={connectionStatus}
        health={health}
        isWsConnected={isWsConnected}
        onRefresh={refreshStatus}
      />

      <div className="flex flex-1">
        {/* Left Navigation Sidebar */}
        <Sidebar currentTab={currentTab} onTabChange={setCurrentTab} />

        {/* Main Content View */}
        <main className="flex-1 p-6 overflow-y-auto max-w-[1600px] mx-auto w-full">
          {currentTab === 'dashboard' && (
            <Dashboard
              ticks={ticks}
              activeCandles={activeCandles}
              connectionStatus={connectionStatus}
              onRefresh={refreshStatus}
            />
          )}

          {currentTab === 'charts' && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-slate-400">Select Instrument:</span>
                <div className="flex items-center gap-1 bg-terminal-card border border-terminal-border p-1 rounded-lg">
                  {(['HDFCBANK', 'ICICIBANK'] as const).map((sym) => (
                    <button
                      key={sym}
                      type="button"
                      onClick={() => setChartSymbol(sym)}
                      className={`px-3 py-1 text-xs font-mono rounded font-medium transition-all ${
                        chartSymbol === sym
                          ? 'bg-terminal-accent text-slate-900 shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
              <div className="h-[650px]">
                <CandleChart symbol={chartSymbol} activeCandle={activeCandle} />
              </div>
            </div>
          )}

          {currentTab === 'signals' && <SignalHistory />}

          {currentTab === 'backtesting' && <BacktestPanel />}

          {currentTab === 'logs' && (
            <div className="rounded-xl border border-terminal-border bg-terminal-card p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-terminal-border/60">
                <div className="flex items-center gap-2">
                  <Terminal size={18} className="text-terminal-accent" />
                  <h2 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                    Full System & Connection Audit Trail (SQLite)
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={loadLogs}
                  disabled={loadingLogs}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-terminal-border text-xs font-mono text-slate-300 hover:bg-slate-800"
                >
                  <RefreshCw size={13} className={loadingLogs ? 'animate-spin' : ''} />
                  <span>Refresh Logs</span>
                </button>
              </div>

              <div className="overflow-x-auto">
                {logs.length === 0 ? (
                  <div className="py-8 text-center text-xs font-mono text-slate-500">
                    Click Refresh Logs or wait for connection events.
                  </div>
                ) : (
                  <table className="w-full text-left font-mono text-xs">
                    <thead>
                      <tr className="text-slate-500 border-b border-terminal-border/60 pb-2">
                        <th className="py-2">ID</th>
                        <th className="py-2">Timestamp (IST)</th>
                        <th className="py-2">Provider</th>
                        <th className="py-2">State</th>
                        <th className="py-2">Message</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-border/20">
                      {logs.map((log) => (
                        <tr key={log.id} className="text-slate-300">
                          <td className="py-2 text-slate-600">#{log.id}</td>
                          <td className="py-2 text-slate-400 whitespace-nowrap">{log.timestamp}</td>
                          <td className="py-2 text-slate-400">{log.provider}</td>
                          <td className="py-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
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
                          <td className="py-2 text-slate-200">{log.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {currentTab === 'settings' && <SettingsPanel />}
        </main>
      </div>
    </div>
  );
}

