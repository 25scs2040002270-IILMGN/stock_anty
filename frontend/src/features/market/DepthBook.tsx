'use client';

import React from 'react';
import { DepthLevel } from '../../types/market';
import { formatINR, formatQuantity } from '../../utils/formatters';

interface Props {
  bids?: DepthLevel[];
  asks?: DepthLevel[];
}

export const DepthBook: React.FC<Props> = ({ bids = [], asks = [] }) => {
  const maxLevels = 5;
  const bidRows = bids.slice(0, maxLevels);
  const askRows = asks.slice(0, maxLevels);

  const hasData = bidRows.length > 0 || askRows.length > 0;

  if (!hasData) {
    return (
      <div className="py-4 text-center text-xs text-slate-500 font-mono">
        Market depth waiting for live feed...
      </div>
    );
  }

  // Calculate maximum volume for depth bar width
  const allVols = [...bidRows, ...askRows].map((l) => l.quantity || 0);
  const maxVol = Math.max(...allVols, 1);

  return (
    <div className="text-xs font-mono select-none">
      <div className="grid grid-cols-2 gap-2 text-slate-400 border-b border-terminal-border/60 pb-1 mb-1 font-semibold">
        <div className="flex justify-between px-1">
          <span>Qty</span>
          <span>Bid</span>
        </div>
        <div className="flex justify-between px-1">
          <span>Ask</span>
          <span>Qty</span>
        </div>
      </div>

      <div className="space-y-0.5">
        {Array.from({ length: maxLevels }).map((_, idx) => {
          const bid = bidRows[idx];
          const ask = askRows[idx];

          const bidWidth = bid ? Math.min(100, Math.round((bid.quantity / maxVol) * 100)) : 0;
          const askWidth = ask ? Math.min(100, Math.round((ask.quantity / maxVol) * 100)) : 0;

          return (
            <div key={idx} className="grid grid-cols-2 gap-2 h-5 items-center">
              {/* Bid Side */}
              <div className="relative flex justify-between items-center px-1 h-full overflow-hidden rounded-sm">
                <div
                  className="absolute right-0 top-0 bottom-0 bg-emerald-500/15 pointer-events-none transition-all duration-300"
                  style={{ width: `${bidWidth}%` }}
                />
                <span className="relative z-10 text-slate-300">
                  {bid ? formatQuantity(bid.quantity) : '--'}
                </span>
                <span className="relative z-10 font-medium text-emerald-400">
                  {bid ? formatINR(bid.price) : '--'}
                </span>
              </div>

              {/* Ask Side */}
              <div className="relative flex justify-between items-center px-1 h-full overflow-hidden rounded-sm">
                <div
                  className="absolute left-0 top-0 bottom-0 bg-rose-500/15 pointer-events-none transition-all duration-300"
                  style={{ width: `${askWidth}%` }}
                />
                <span className="relative z-10 font-medium text-rose-400">
                  {ask ? formatINR(ask.price) : '--'}
                </span>
                <span className="relative z-10 text-slate-300">
                  {ask ? formatQuantity(ask.quantity) : '--'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

