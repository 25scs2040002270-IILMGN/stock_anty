'use client';

import React, { useState, useEffect } from 'react';
import { ConnectionStatus, HealthStatus } from '../types/market';
import { StatusBadge } from './StatusBadge';
import { Activity, Clock, RefreshCw } from 'lucide-react';

interface Props {
  status?: ConnectionStatus | null;
  health?: HealthStatus | null;
  isWsConnected: boolean;
  onRefresh?: () => void;
}

export const Header: React.FC<Props> = ({ status, health, isWsConnected, onRefresh }) => {
  const [istTime, setIstTime] = useState<string>('--:--:--');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setIstTime(
        now.toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const marketOpen = health?.market_open ?? status?.is_market_session_open ?? false;
  const connectionState = status?.state || (isWsConnected ? 'STALE' : 'DISCONNECTED');

  return (
    <header className="h-16 border-b border-terminal-border bg-terminal-card/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Brand & Market Session */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-terminal-accent/20 border border-terminal-accent/40 flex items-center justify-center">
            <Activity size={16} className="text-terminal-accent" />
          </div>
          <div>
            <h1 className="text-base font-bold font-mono tracking-tight text-white">
              MARKETPULSE <span className="text-terminal-accent">AI</span>
            </h1>
            <p className="text-[10px] text-slate-400 font-mono">Personal NSE Equities Terminal</p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono">
          <span
            className={`h-2 w-2 rounded-full ${
              marketOpen ? 'bg-emerald-400' : 'bg-slate-500'
            }`}
          />
          <span className="text-slate-300">
            {marketOpen ? 'NSE Market Open' : 'NSE Market Closed'}
          </span>
        </div>
      </div>

      {/* Right: Clock & Connection Health */}
      <div className="flex items-center gap-4">
        {/* IST Clock */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-lg bg-terminal-bg border border-terminal-border/80 text-xs font-mono text-slate-300">
          <Clock size={13} className="text-slate-400" />
          <span>{istTime} IST</span>
        </div>

        {/* WebSocket / Provider State Badge */}
        <div className="flex items-center gap-2">
          <StatusBadge state={connectionState} />
        </div>

        {/* Refresh button */}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            title="Refresh status"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-terminal-border transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        )}
      </div>
    </header>
  );
};

