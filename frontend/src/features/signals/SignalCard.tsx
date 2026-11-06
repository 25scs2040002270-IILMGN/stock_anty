'use client';

import React, { useState } from 'react';
import { SignalResponse } from '../../types/market';
import { formatINR, formatPercent } from '../../utils/formatters';
import {
  TrendingUp,
  TrendingDown,
  PauseCircle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  SlidersHorizontal,
  Info,
  Clock,
  Zap,
  Target,
  AlertTriangle
} from 'lucide-react';

interface Props {
  signal: SignalResponse | null;
  loading?: boolean;
  onRefresh?: () => void;
}

export const SignalCard: React.FC<Props> = ({ signal, loading = false, onRefresh }) => {
  const [showScoreDetails, setShowScoreDetails] = useState<boolean>(false);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false);

  if (loading && !signal) {
    return (
      <div className="p-6 rounded-xl bg-terminal-card border border-terminal-border text-center text-xs font-mono text-slate-500 animate-pulse">
        Evaluating multi-timeframe indicators & liquidity sweeps...
      </div>
    );
  }

  if (!signal) {
    return (
      <div className="p-6 rounded-xl bg-terminal-card border border-terminal-border text-center text-xs font-mono text-slate-500">
        Select an instrument or wait for candle confirmation to view quantitative signals.
      </div>
    );
  }

  const isBuy = signal.direction === 'BUY';
  const isSell = signal.direction === 'SELL';
  const isWait = signal.direction === 'WAIT';

  const score = signal.scoring_breakdown?.total_score ?? 0;
  const sizing = signal.position_sizing;

  return (
    <div className="rounded-xl border border-terminal-border bg-terminal-card overflow-hidden">
      {/* Top Banner: Signal Direction & Score */}
      <div
        className={`p-5 flex flex-wrap items-center justify-between gap-4 border-b ${
          isBuy
            ? 'bg-emerald-950/40 border-emerald-500/30'
            : isSell
            ? 'bg-rose-950/40 border-rose-500/30'
            : 'bg-slate-900/60 border-terminal-border'
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`h-10 w-10 rounded-xl flex items-center justify-center font-bold font-mono text-lg ${
              isBuy
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : isSell
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-lg shadow-rose-500/10'
                : 'bg-slate-800 text-amber-400 border border-slate-700'
            }`}
          >
            {isBuy ? <TrendingUp size={22} /> : isSell ? <TrendingDown size={22} /> : <PauseCircle size={22} />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span
                className={`text-xl font-extrabold font-mono tracking-wider ${
                  isBuy ? 'text-emerald-400' : isSell ? 'text-rose-400' : 'text-amber-400'
                }`}
              >
                {signal.direction}
              </span>
              <span className="text-xs font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                {signal.symbol}
              </span>
            </div>
            <p className="text-[11px] font-mono text-slate-400 mt-0.5 flex items-center gap-1.5">
              <Clock size={12} />
              <span>Forecast horizon: ~{signal.expected_validity_minutes} min | Manual broker execution</span>
            </p>
          </div>
        </div>

        {/* Technical Score Badge */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
              Alignment Score
            </span>
            <div className="flex items-baseline justify-end gap-1">
              <span
                className={`text-2xl font-extrabold font-mono ${
                  score >= 70
                    ? 'text-emerald-400'
                    : score >= 50
                    ? 'text-amber-400'
                    : 'text-slate-400'
                }`}
              >
                {score}
              </span>
              <span className="text-xs font-mono text-slate-500">/100</span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowScoreDetails((prev) => !prev)}
            className="p-1.5 rounded-lg border border-terminal-border text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
            title="Inspect score breakdown"
          >
            {showScoreDetails ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* Score Explanation / Disclaimer (Collapsible) */}
      {showScoreDetails && (
        <div className="p-4 bg-terminal-bg/90 border-b border-terminal-border text-xs font-mono space-y-2">
          <div className="flex items-start gap-2 text-slate-400 bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
            <Info size={14} className="text-terminal-accent shrink-0 mt-0.5" />
            <p className="text-[11px] text-slate-300">
              <strong>Transparent Scoring System:</strong> This score represents rule alignment across multi-timeframe indicators and liquidity factors.
              <span className="text-amber-400 block mt-0.5">
                The score is NOT a probability or guaranteed win rate.
              </span>
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
            <div className="p-2 rounded bg-terminal-card border border-terminal-border/40">
              <span className="text-slate-500 block">15m Macro Trend:</span>
              <span className="text-slate-200 font-semibold">+{signal.scoring_breakdown.trend_15m_score} pts</span>
            </div>
            <div className="p-2 rounded bg-terminal-card border border-terminal-border/40">
              <span className="text-slate-500 block">5m Setup & VWAP:</span>
              <span className="text-slate-200 font-semibold">+{signal.scoring_breakdown.setup_5m_score + signal.scoring_breakdown.vwap_score} pts</span>
            </div>
            <div className="p-2 rounded bg-terminal-card border border-terminal-border/40">
              <span className="text-slate-500 block">1m Timing & RSI:</span>
              <span className="text-slate-200 font-semibold">+{signal.scoring_breakdown.entry_1m_score + signal.scoring_breakdown.rsi_score} pts</span>
            </div>
            <div className="p-2 rounded bg-terminal-card border border-terminal-border/40">
              <span className="text-slate-500 block">Liquidity Penalty:</span>
              <span className="text-rose-400 font-semibold">-{signal.scoring_breakdown.liquidity_penalty} pts</span>
            </div>
          </div>
        </div>
      )}

      {/* Trade Parameters: Risk, Entry, SL, Target */}
      {!isWait && (
        <div className="p-5 border-b border-terminal-border/60 bg-terminal-card">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Target size={14} className="text-terminal-accent" />
              Calculated Risk & Execution Parameters
            </h4>
            <span className="text-[10px] font-mono text-slate-500">
              Lot Size: 1 share (NSE Equity)
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            {/* Entry Zone */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
              <span className="text-[10px] text-slate-500 block mb-0.5">Entry Zone</span>
              <span className="text-sm font-bold text-slate-100">
                ₹{formatINR(signal.entry_zone.low)} - {formatINR(signal.entry_zone.high)}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Target Entry: ₹{formatINR(signal.entry_zone.center)}
              </span>
            </div>

            {/* Stop Loss */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
              <span className="text-[10px] text-slate-500 block mb-0.5">Stop Loss</span>
              <span className="text-sm font-bold text-rose-400">
                ₹{formatINR(signal.stop_loss)}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Risk/sh: ₹{formatINR(Math.abs(signal.entry_zone.center - signal.stop_loss))}
              </span>
            </div>

            {/* Target */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
              <span className="text-[10px] text-slate-500 block mb-0.5">Target</span>
              <span className="text-sm font-bold text-emerald-400">
                ₹{formatINR(signal.target)}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Reward/sh: ₹{formatINR(Math.abs(signal.target - signal.entry_zone.center))}
              </span>
            </div>

            {/* Risk / Reward & Position */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
              <span className="text-[10px] text-slate-500 block mb-0.5">Risk / Reward</span>
              <span className="text-sm font-bold text-terminal-accent">
                1 : {signal.risk_reward_ratio.toFixed(2)}
              </span>
              {sizing && (
                <span className="text-[10px] text-slate-300 block mt-0.5">
                  Size: {sizing.suggested_shares} shares (Risk ₹{formatINR(sizing.monetary_risk_actual)})
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Multi-Timeframe Strategy Explanations */}
      <div className="p-5 space-y-3 text-xs font-mono">
        <div className="flex items-center justify-between pb-2 border-b border-terminal-border/40">
          <span className="font-bold text-slate-300 uppercase tracking-wide flex items-center gap-1.5">
            <Zap size={14} className="text-amber-400" />
            Multi-Timeframe Strategy Alignment
          </span>
          <button
            type="button"
            onClick={() => setShowTechnicalDetails((prev) => !prev)}
            className="text-[11px] text-terminal-accent hover:underline flex items-center gap-1"
          >
            <span>{showTechnicalDetails ? 'Collapse Technicals' : 'Expand All Indicators'}</span>
            {showTechnicalDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>

        {/* 15m Trend */}
        <div className="flex items-start gap-2">
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400 shrink-0 mt-0.5">
            15M
          </span>
          <p className="text-slate-300">{signal.trend_15m_explanation}</p>
        </div>

        {/* 5m Setup */}
        <div className="flex items-start gap-2">
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400 shrink-0 mt-0.5">
            5M
          </span>
          <p className="text-slate-300">{signal.setup_5m_explanation}</p>
        </div>

        {/* 1m Entry */}
        <div className="flex items-start gap-2">
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400 shrink-0 mt-0.5">
            1M
          </span>
          <p className="text-slate-300">{signal.entry_1m_explanation}</p>
        </div>

        {/* Liquidity Sweep Status */}
        <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border/80 flex items-start gap-2.5">
          <ShieldAlert size={16} className="text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="text-[11px] font-bold text-slate-200 block">
              Liquidity & Fakeout Risk Assessment
            </span>
            <p className="text-[11px] text-slate-400 mt-0.5">{signal.liquidity_sweep_risk}</p>
          </div>
        </div>

        {/* Expanded Technical Details */}
        {showTechnicalDetails && (
          <div className="pt-2 border-t border-terminal-border/40 space-y-2 text-[11px]">
            <div>
              <span className="text-slate-500 font-semibold">EMA Alignment: </span>
              <span className="text-slate-300">{signal.ema_explanation}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold">VWAP Status: </span>
              <span className="text-slate-300">{signal.vwap_explanation}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold">RSI Momentum: </span>
              <span className="text-slate-300">{signal.rsi_explanation}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold">Volume Confirmation: </span>
              <span className="text-slate-300">{signal.volume_confirmation}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold">Support & Resistance: </span>
              <span className="text-slate-300">{signal.support_resistance_explanation}</span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold">Candlestick Pattern: </span>
              <span className="text-slate-300">{signal.candlestick_confirmation}</span>
            </div>
            <div className="p-2 rounded bg-rose-950/20 border border-rose-500/20 text-rose-300">
              <span className="font-semibold text-rose-400">Invalidation Condition: </span>
              <span>{signal.invalidation_condition}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

