'use client';

import React, { useState, useEffect } from 'react';
import {
  fetchAuthStatus,
  fetchLoginUrl,
  submitManualToken,
  fetchRiskSettings,
  updateRiskSettings,
  fetchDailyRiskSummary,
} from '../../services/api';
import { RiskSettings } from '../../types/market';
import { notifications } from '../../utils/notifications';
import { formatINR } from '../../utils/formatters';
import {
  Key,
  ShieldCheck,
  AlertCircle,
  ExternalLink,
  CheckCircle,
  Lock,
  Sliders,
  DollarSign,
  Percent,
  Bell,
  Volume2,
  Calendar,
} from 'lucide-react';

export const SettingsPanel: React.FC = () => {
  const [authStatus, setAuthStatus] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [manualToken, setManualToken] = useState<string>('');
  const [submittingToken, setSubmittingToken] = useState<boolean>(false);
  const [tokenMessage, setTokenMessage] = useState<{ text: string; error: boolean } | null>(null);

  // Risk parameters
  const [riskSettings, setRiskSettings] = useState<RiskSettings>({
    trading_capital: 100000.0,
    risk_percentage: 1.0,
    max_risk_reward_min: 1.5,
    lot_size: 1
  });
  const [savingRisk, setSavingRisk] = useState<boolean>(false);
  const [riskMessage, setRiskMessage] = useState<string | null>(null);

  // Notifications & Sound
  const [soundEnabled, setSoundEnabled] = useState<boolean>(notifications.isSoundEnabled());
  const [notifyEnabled, setNotifyEnabled] = useState<boolean>(notifications.isBrowserNotificationEnabled());

  // Daily Risk Summary
  const [dailySummary, setDailySummary] = useState<any | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [auth, risk, daily] = await Promise.allSettled([
        fetchAuthStatus(),
        fetchRiskSettings(),
        fetchDailyRiskSummary(),
      ]);
      if (auth.status === 'fulfilled') setAuthStatus(auth.value);
      if (risk.status === 'fulfilled') setRiskSettings(risk.value);
      if (daily.status === 'fulfilled') setDailySummary(daily.value);
    } catch (e) {
      // offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOAuthLogin = async () => {
    try {
      const res = await fetchLoginUrl();
      if (res.authorization_url) {
        window.open(res.authorization_url, '_blank');
      }
    } catch (e: any) {
      alert(`Could not generate login URL: ${e.message}`);
    }
  };

  const handleTokenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualToken.trim()) return;

    setSubmittingToken(true);
    setTokenMessage(null);
    try {
      const res = await submitManualToken(manualToken.trim());
      setTokenMessage({ text: res.message || 'Token updated successfully', error: false });
      setManualToken('');
      loadData();
    } catch (err: any) {
      setTokenMessage({ text: err.message || 'Failed to update token', error: true });
    } finally {
      setSubmittingToken(false);
    }
  };

  const handleRiskSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingRisk(true);
    setRiskMessage(null);
    try {
      await updateRiskSettings(riskSettings);
      setRiskMessage('Risk parameters saved successfully to SQLite database.');
      setTimeout(() => setRiskMessage(null), 4000);
    } catch (err: any) {
      setRiskMessage(`Error saving settings: ${err.message}`);
    } finally {
      setSavingRisk(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold font-mono text-white flex items-center gap-2">
          <Key className="text-terminal-accent" size={20} />
          MarketPulse AI Settings & Risk Parameters
        </h2>
        <p className="text-xs text-slate-400 font-mono mt-1">
          Configure Upstox broker authentication and personal quantitative risk management parameters.
        </p>
      </div>

      {/* Security Banner */}
      <div className="p-4 rounded-xl border border-terminal-border bg-terminal-card/80 flex items-start gap-3">
        <Lock className="text-emerald-400 mt-0.5 shrink-0" size={18} />
        <div className="text-xs font-mono space-y-1">
          <p className="text-slate-200 font-semibold">Strict Backend Security Standard</p>
          <p className="text-slate-400">
            All API secrets and OAuth tokens are strictly stored and processed on the private FastAPI backend.
            Access tokens are never exposed to frontend JavaScript or client-side storage.
          </p>
        </div>
      </div>

      {/* Risk Management Configuration Card */}
      <div className="rounded-xl border border-terminal-border bg-terminal-card p-5">
        <h3 className="text-sm font-semibold font-mono text-slate-200 mb-2 pb-2 border-b border-terminal-border/60 flex items-center gap-2">
          <Sliders size={16} className="text-terminal-accent" />
          Quantitative Risk Management Settings
        </h3>
        <p className="text-[11px] font-mono text-slate-400 mb-4">
          Positions are calculated using: <code className="text-slate-300">Size = (Capital × Risk%) / |Entry - SL|</code>.
          Never assumes unlimited capital.
        </p>

        <form onSubmit={handleRiskSubmit} className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div>
            <label className="text-slate-400 block mb-1">Trading Capital (INR)</label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-slate-500 font-mono">₹</span>
              <input
                type="number"
                min="1000"
                step="5000"
                value={riskSettings.trading_capital}
                onChange={(e) =>
                  setRiskSettings({ ...riskSettings, trading_capital: parseFloat(e.target.value) || 0 })
                }
                className="w-full pl-7 pr-3 py-2 rounded-lg bg-terminal-bg border border-terminal-border text-slate-200 focus:outline-none focus:border-terminal-accent"
              />
            </div>
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Risk per Trade (%)</label>
            <div className="relative">
              <input
                type="number"
                min="0.1"
                max="10.0"
                step="0.1"
                value={riskSettings.risk_percentage}
                onChange={(e) =>
                  setRiskSettings({ ...riskSettings, risk_percentage: parseFloat(e.target.value) || 0 })
                }
                className="w-full px-3 py-2 rounded-lg bg-terminal-bg border border-terminal-border text-slate-200 focus:outline-none focus:border-terminal-accent"
              />
              <span className="absolute right-3 top-2 text-slate-500 font-mono">%</span>
            </div>
          </div>

          <div>
            <label className="text-slate-400 block mb-1">Min. Risk/Reward Ratio</label>
            <input
              type="number"
              min="1.0"
              max="5.0"
              step="0.1"
              value={riskSettings.max_risk_reward_min}
              onChange={(e) =>
                setRiskSettings({ ...riskSettings, max_risk_reward_min: parseFloat(e.target.value) || 0 })
              }
              className="w-full px-3 py-2 rounded-lg bg-terminal-bg border border-terminal-border text-slate-200 focus:outline-none focus:border-terminal-accent"
            />
          </div>

          <div className="sm:col-span-3 flex items-center justify-between pt-2">
            <button
              type="submit"
              disabled={savingRisk}
              className="px-4 py-2 rounded-lg bg-terminal-accent text-slate-900 font-bold hover:bg-sky-400 transition-colors"
            >
              {savingRisk ? 'Saving...' : 'Save Risk Parameters'}
            </button>
            {riskMessage && (
              <span className="text-xs font-mono text-emerald-400">{riskMessage}</span>
            )}
          </div>
        </form>
      </div>

      {/* Auth Status Card */}
      <div className="rounded-xl border border-terminal-border bg-terminal-card p-5">
        <h3 className="text-sm font-semibold font-mono text-slate-200 mb-4 pb-2 border-b border-terminal-border/60">
          Broker Integration Status (Upstox V3)
        </h3>

        {loading ? (
          <div className="text-xs font-mono text-slate-500 py-3">Loading credentials state...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {/* API Key */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border/60">
              <span className="text-[11px] font-mono text-slate-500 block mb-1">API Key (Client ID)</span>
              <div className="flex items-center gap-2">
                {authStatus?.credentials?.has_api_key ? (
                  <CheckCircle size={16} className="text-emerald-400" />
                ) : (
                  <AlertCircle size={16} className="text-amber-400" />
                )}
                <span className="text-xs font-mono font-medium text-slate-200">
                  {authStatus?.credentials?.has_api_key ? 'Configured' : 'Missing in .env'}
                </span>
              </div>
            </div>

            {/* API Secret */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border/60">
              <span className="text-[11px] font-mono text-slate-500 block mb-1">API Secret</span>
              <div className="flex items-center gap-2">
                {authStatus?.credentials?.has_api_secret ? (
                  <CheckCircle size={16} className="text-emerald-400" />
                ) : (
                  <AlertCircle size={16} className="text-amber-400" />
                )}
                <span className="text-xs font-mono font-medium text-slate-200">
                  {authStatus?.credentials?.has_api_secret ? 'Configured' : 'Missing in .env'}
                </span>
              </div>
            </div>

            {/* Active Token */}
            <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border/60">
              <span className="text-[11px] font-mono text-slate-500 block mb-1">Live Access Token</span>
              <div className="flex items-center gap-2">
                {authStatus?.credentials?.has_active_token ? (
                  <CheckCircle size={16} className="text-emerald-400" />
                ) : (
                  <AlertCircle size={16} className="text-slate-500" />
                )}
                <span className="text-xs font-mono font-medium text-slate-200">
                  {authStatus?.credentials?.has_active_token ? 'Active on Backend' : 'Not Authenticated'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* OAuth Dialog Action */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-lg bg-terminal-bg border border-terminal-border/60 mb-6">
          <div>
            <h4 className="text-xs font-mono font-semibold text-slate-200">Official Upstox OAuth Flow</h4>
            <p className="text-[11px] font-mono text-slate-400 mt-0.5">
              Opens the official Upstox authorization dialogue to log in with mobile OTP and MPIN.
            </p>
          </div>
          <button
            type="button"
            onClick={handleOAuthLogin}
            className="flex items-center gap-2 px-4 py-2 text-xs font-mono font-semibold text-slate-900 bg-terminal-accent hover:bg-sky-400 rounded-lg transition-colors shrink-0"
          >
            <span>Login with Upstox</span>
            <ExternalLink size={14} />
          </button>
        </div>

        {/* Manual Token Fallback */}
        <div className="pt-4 border-t border-terminal-border/60">
          <h4 className="text-xs font-mono font-semibold text-slate-200 mb-1">
            Manual Token Injection (Alternative)
          </h4>
          <p className="text-[11px] font-mono text-slate-400 mb-3">
            If you already generated an access token via Upstox API or developer portal today, you can inject it directly:
          </p>

          <form onSubmit={handleTokenSubmit} className="space-y-3">
            <input
              type="password"
              placeholder="Paste raw Upstox access token..."
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              className="w-full px-3 py-2 text-xs font-mono rounded-lg bg-terminal-bg border border-terminal-border text-slate-200 placeholder-slate-600 focus:outline-none focus:border-terminal-accent"
            />
            <div className="flex items-center justify-between">
              <button
                type="submit"
                disabled={submittingToken || !manualToken.trim()}
                className="px-4 py-2 text-xs font-mono font-medium rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 disabled:opacity-50 transition-colors"
              >
                {submittingToken ? 'Updating...' : 'Save Token in Secure Database'}
              </button>

              {tokenMessage && (
                <span
                  className={`text-xs font-mono ${
                    tokenMessage.error ? 'text-rose-400' : 'text-emerald-400'
                  }`}
                >
                  {tokenMessage.text}
                </span>
              )}
            </div>
          </form>
        </div>
      </div>

      {/* Daily Risk Summary Card */}
      {dailySummary && (
        <div className="rounded-xl border border-terminal-border bg-terminal-card p-5 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-terminal-border/60">
            <h3 className="text-sm font-semibold font-mono text-slate-200 flex items-center gap-2">
              <Calendar size={16} className="text-terminal-accent" />
              Daily Risk &amp; Signals Monitor (IST Today)
            </h3>
            <span className="text-[11px] font-mono text-slate-500">
              Personal Capital: {formatINR(dailySummary.trading_capital)}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 bg-terminal-bg rounded-lg border border-terminal-border">
              <span className="text-[10px] text-slate-500 uppercase">Signals Generated</span>
              <div className="text-lg font-bold text-white mt-1">
                {dailySummary.total_signals}
              </div>
              <span className="text-[10px] text-slate-500">
                {dailySummary.buy_count} BUY • {dailySummary.sell_count} SELL • {dailySummary.wait_count} WAIT
              </span>
            </div>

            <div className="p-3 bg-terminal-bg rounded-lg border border-terminal-border">
              <span className="text-[10px] text-slate-500 uppercase">Max Risk Budget / Trade</span>
              <div className="text-lg font-bold text-amber-400 mt-1">
                {formatINR(dailySummary.max_monetary_risk_per_trade)}
              </div>
              <span className="text-[10px] text-slate-500">
                {dailySummary.risk_percentage}% of account
              </span>
            </div>

            <div className="p-3 bg-terminal-bg rounded-lg border border-terminal-border">
              <span className="text-[10px] text-slate-500 uppercase">Target Hits Today</span>
              <div className="text-lg font-bold text-emerald-400 mt-1">
                {dailySummary.hypothetical_target_hits}
              </div>
              <span className="text-[10px] text-slate-500">
                Objective target reached
              </span>
            </div>

            <div className="p-3 bg-terminal-bg rounded-lg border border-terminal-border">
              <span className="text-[10px] text-slate-500 uppercase">Stop Losses Today</span>
              <div className="text-lg font-bold text-rose-400 mt-1">
                {dailySummary.hypothetical_stop_losses}
              </div>
              <span className="text-[10px] text-slate-500">
                Objective stop loss crossed
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Notifications & Audio Alerts */}
      <div className="rounded-xl border border-terminal-border bg-terminal-card p-5 space-y-4">
        <h3 className="text-sm font-semibold font-mono text-slate-200 pb-2 border-b border-terminal-border/60 flex items-center gap-2">
          <Bell size={16} className="text-terminal-accent" />
          Alerts &amp; Audio Notifications
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-3.5 bg-terminal-bg rounded-lg border border-terminal-border flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 font-semibold text-slate-200">
                <Volume2 size={16} className="text-terminal-accent" />
                <span>Synthetic Audio Chime</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Plays dual-tone synthesizer chime on confirmed BUY/SELL signals.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => notifications.playSignalChime(true)}
                className="px-2 py-1 text-[10px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                Test
              </button>
              <button
                type="button"
                onClick={() => {
                  const next = !soundEnabled;
                  notifications.setSoundEnabled(next);
                  setSoundEnabled(next);
                }}
                className={`px-3 py-1 text-xs rounded font-bold ${
                  soundEnabled
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {soundEnabled ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>

          <div className="p-3.5 bg-terminal-bg rounded-lg border border-terminal-border flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 font-semibold text-slate-200">
                <Bell size={16} className="text-terminal-accent" />
                <span>Browser Push Notifications</span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                HTML5 desktop push notification when new signal arrives.
              </p>
            </div>
            <div>
              <button
                type="button"
                onClick={async () => {
                  const granted = await notifications.requestNotificationPermission();
                  setNotifyEnabled(granted);
                  if (granted) {
                    notifications.notifySignal('HDFCBANK', 'BUY', 1600.0, 85);
                  }
                }}
                className={`px-3 py-1 text-xs rounded font-bold ${
                  notifyEnabled
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                {notifyEnabled ? 'ALLOWED' : 'ENABLE'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration Constraints */}
      <div className="rounded-xl border border-terminal-border bg-terminal-card p-5">
        <h3 className="text-sm font-semibold font-mono text-slate-200 mb-3 pb-2 border-b border-terminal-border/60 flex items-center gap-2">
          <ShieldCheck size={16} className="text-emerald-400" />
          Strict Instrument Policy Configuration
        </h3>

        <div className="space-y-2 text-xs font-mono">
          <div className="flex justify-between py-1 border-b border-terminal-border/30">
            <span className="text-slate-400">Supported Equities:</span>
            <span className="text-emerald-400 font-semibold">HDFCBANK, ICICIBANK (Only)</span>
          </div>
          <div className="flex justify-between py-1 border-b border-terminal-border/30">
            <span className="text-slate-400">Prohibited Symbol Filter:</span>
            <span className="text-rose-400 font-semibold">RELIANCE (Hard-Blocked)</span>
          </div>
          <div className="flex justify-between py-1 border-b border-terminal-border/30">
            <span className="text-slate-400">Exchange / Segment:</span>
            <span className="text-slate-200">NSE EQ (National Stock Exchange of India)</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-slate-400">Timezone Context:</span>
            <span className="text-slate-200">Asia/Kolkata (IST, UTC+05:30)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
