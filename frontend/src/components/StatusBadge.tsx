import React from 'react';
import { ConnectionState } from '../types/market';

interface Props {
  state?: ConnectionState;
  className?: string;
  showDot?: boolean;
}

export const StatusBadge: React.FC<Props> = ({ state = 'DISCONNECTED', className = '', showDot = true }) => {
  const configs: Record<ConnectionState, { label: string; bg: string; text: string; dot: string; pulse: boolean }> = {
    LIVE: {
      label: 'LIVE',
      bg: 'bg-emerald-950/60 border-emerald-500/40',
      text: 'text-emerald-400',
      dot: 'bg-emerald-400',
      pulse: true,
    },
    DELAYED: {
      label: 'DELAYED',
      bg: 'bg-amber-950/60 border-amber-500/40',
      text: 'text-amber-400',
      dot: 'bg-amber-400',
      pulse: false,
    },
    STALE: {
      label: 'STALE',
      bg: 'bg-yellow-950/60 border-yellow-500/40',
      text: 'text-yellow-400',
      dot: 'bg-yellow-400',
      pulse: false,
    },
    DISCONNECTED: {
      label: 'DISCONNECTED',
      bg: 'bg-slate-900/80 border-slate-700/50',
      text: 'text-slate-400',
      dot: 'bg-slate-500',
      pulse: false,
    },
  };

  const current = configs[state] || configs.DISCONNECTED;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium border ${current.bg} ${current.text} ${className}`}
    >
      {showDot && (
        <span className="relative flex h-2 w-2">
          {current.pulse && (
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${current.dot} opacity-75`} />
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${current.dot}`} />
        </span>
      )}
      {current.label}
    </span>
  );
};

