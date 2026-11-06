'use client';

import React, { useState } from 'react';
import { MarketTick } from '../types/market';
import { formatINR, formatQuantity, formatPercent, formatEpochTime } from '../utils/formatters';
import { DepthBook } from '../features/market/DepthBook';
import { TrendingUp, TrendingDown, Layers, Clock } from 'lucide-react';

interface Props {
  symbol: 'HDFCBANK' | 'ICICIBANK';
  instrumentKey: string;
  name: string;
  tick?: MarketTick | null;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const PriceCard: React.FC<Props> = ({
  symbol,
  instrumentKey,
  name,
  tick,
  isSelected = false,
  onSelect,
}) => {
  const [showDepth, setShowDepth] = useState<boolean>(false);

  const hasData = Boolean(tick && tick.ltp > 0);
  const ltp = hasData ? tick!.ltp : null;
  const ohlc = tick?.ohlc;
  const prevClose = ohlc?.close || null;

  // Day change calculation
  let priceChange: number | null = null;
  let percentChange: number | null = null;
  if (ltp !== null && prevClose !== null && prevClose > 0) {
    priceChange = ltp - prevClose;
    percentChange = (priceChange / prevClose) * 100;
  }

  const isUp = priceChange !== null ? priceChange >= 0 : true;

  return (
    <div
      onClick={onSelect}
      className={`rounded-xl border transition-all duration-200 cursor-pointer overflow-hidden p-5 ${
        isSelected
          ? 'bg-terminal-card border-terminal-accent/60 shadow-lg shadow-terminal-accent/5 ring-1 ring-terminal-accent/30'
          : 'bg-terminal-card/70 border-terminal-border hover:border-terminal-border/90 hover:bg-terminal-card'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-xl font-bold font-mono tracking-tight text-white">{symbol}</h3>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60">
              NSE EQ
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{name}</p>
          <p className="text-[10px] text-slate-500 font-mono mt-0.5">{instrumentKey}</p>
        </div>

        {/* Change Indicator */}
        {hasData && percentChange !== null ? (
          <div
            className={`flex items-center gap-1 text-xs font-mono font-semibold px-2 py-1 rounded-md ${
              isUp ? 'text-emerald-400 bg-emerald-950/40' : 'text-rose-400 bg-rose-950/40'
            }`}
          >
            {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <span>{formatPercent(percentChange)}</span>
          </div>
        ) : (
          <span className="text-xs font-mono text-slate-500 bg-slate-800/40 px-2 py-1 rounded-md">
            --
          </span>
        )}
      </div>

      {/* Main LTP */}
      <div className="my-4">
        <div className="flex items-baseline gap-2">
          <span className="text-xs text-slate-400 font-mono">₹</span>
          <span className="text-3xl font-extrabold font-mono tracking-tight text-slate-100">
            {formatINR(ltp)}
          </span>
          {priceChange !== null && (
            <span
              className={`text-sm font-mono font-medium ${
                isUp ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              ({isUp ? '+' : ''}{formatINR(priceChange)})
            </span>
          )}
        </div>
        {!hasData && (
          <p className="text-[11px] text-amber-400/80 font-mono mt-1">
            Waiting for live market tick...
          </p>
        )}
      </div>

      {/* OHLC Mini Grid */}
      <div className="grid grid-cols-4 gap-2 py-2 px-3 rounded-lg bg-terminal-bg/80 border border-terminal-border/40 text-[11px] font-mono mb-3">
        <div>
          <span className="text-slate-500 block">Open</span>
          <span className="text-slate-300 font-medium">{formatINR(ohlc?.open)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">High</span>
          <span className="text-slate-300 font-medium">{formatINR(ohlc?.high)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Low</span>
          <span className="text-slate-300 font-medium">{formatINR(ohlc?.low)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Prev. Close</span>
          <span className="text-slate-300 font-medium">{formatINR(ohlc?.close)}</span>
        </div>
      </div>

      {/* Statistics Row */}
      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-terminal-border/40">
        <div>
          <span className="text-slate-500">Vol: </span>
          <span className="text-slate-300 font-medium">
            {formatQuantity(tick?.cumulative_volume)}
          </span>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-slate-500">
          <Clock size={12} />
          <span>{formatEpochTime(tick?.exchange_timestamp)}</span>
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setShowDepth((prev) => !prev);
          }}
          className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded border transition-colors ${
            showDepth
              ? 'bg-terminal-accent/20 border-terminal-accent/50 text-terminal-accent'
              : 'border-terminal-border text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers size={12} />
          <span>Depth</span>
        </button>
      </div>

      {/* Depth Panel (Collapsible) */}
      {showDepth && (
        <div className="mt-3 pt-3 border-t border-terminal-border/60">
          <DepthBook bids={tick?.bids} asks={tick?.asks} />
        </div>
      )}
    </div>
  );
};

