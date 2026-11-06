'use client';

import React from 'react';
import {
  LayoutDashboard,
  LineChart,
  History,
  BarChart3,
  FileText,
  Settings,
  ShieldAlert,
} from 'lucide-react';

export type NavTab = 'dashboard' | 'charts' | 'signals' | 'backtesting' | 'logs' | 'settings';

interface Props {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export const Sidebar: React.FC<Props> = ({ currentTab, onTabChange }) => {
  const navItems: { id: NavTab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
    { id: 'charts', label: 'Live Charts', icon: <LineChart size={18} /> },
    { id: 'signals', label: 'Signal History', icon: <History size={18} /> },
    { id: 'backtesting', label: 'Backtesting', icon: <BarChart3 size={18} /> },
    { id: 'logs', label: 'Feed Logs', icon: <FileText size={18} /> },
    { id: 'settings', label: 'Upstox & Risk', icon: <Settings size={18} /> },
  ];

  return (
    <aside className="w-56 border-r border-terminal-border bg-terminal-card/50 flex flex-col justify-between p-4 shrink-0">
      <div className="space-y-1">
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 px-3 py-2">
          Navigation
        </div>
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-mono font-medium transition-all ${
                isActive
                  ? 'bg-terminal-accent/15 text-terminal-accent border border-terminal-accent/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent'
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Safety Notice Footer */}
      <div className="p-3 rounded-lg bg-terminal-bg/80 border border-terminal-border/60 text-[10px] font-mono text-slate-500 space-y-1">
        <div className="flex items-center gap-1.5 text-slate-400 font-semibold">
          <ShieldAlert size={12} className="text-amber-400" />
          <span>Stage 1 Active</span>
        </div>
        <p>HDFCBANK & ICICIBANK only.</p>
        <p className="text-slate-600">Trading signals blocked.</p>
      </div>
    </aside>
  );
};

