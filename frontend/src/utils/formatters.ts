/**
 * Formats numbers, currencies and timestamps for the trading terminal.
 */

export function formatINR(val?: number | null): string {
  if (val === undefined || val === null || isNaN(val)) return '--';
  return new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
}

export function formatQuantity(val?: number | null): string {
  if (val === undefined || val === null || isNaN(val)) return '--';
  return new Intl.NumberFormat('en-IN').format(val);
}

export function formatPercent(val?: number | null): string {
  if (val === undefined || val === null || isNaN(val)) return '--%';
  const sign = val > 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
}

export function formatEpochTime(epochMs?: number | null): string {
  if (!epochMs) return '--:--:--';
  const d = new Date(epochMs);
  return d.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatEpochDate(epochSec?: number | null): string {
  if (!epochSec) return '--';
  const d = new Date(epochSec * 1000);
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    dateStyle: 'short',
    timeStyle: 'short',
    hour12: false,
  });
}

