/**
 * Technical indicators calculation on Candle arrays for TradingView Lightweight Charts rendering.
 */

import { UTCTimestamp } from 'lightweight-charts';
import { Candle } from '../types/market';

export interface IndicatorPoint {
  time: UTCTimestamp;
  value: number;
}

export function calculateEMA(candles: Candle[], period: number): IndicatorPoint[] {
  if (candles.length < period) return [];

  const k = 2 / (period + 1);
  const result: IndicatorPoint[] = [];

  // Initial SMA
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += candles[i].close;
  }
  let ema = sum / period;
  result.push({
    time: candles[period - 1].open_time as UTCTimestamp,
    value: parseFloat(ema.toFixed(2)),
  });

  for (let i = period; i < candles.length; i++) {
    const c = candles[i];
    ema = c.close * k + ema * (1 - k);
    result.push({
      time: c.open_time as UTCTimestamp,
      value: parseFloat(ema.toFixed(2)),
    });
  }

  return result;
}

export function calculateVWAP(candles: Candle[]): IndicatorPoint[] {
  if (candles.length === 0) return [];

  const result: IndicatorPoint[] = [];
  let cumVol = 0;
  let cumVolPrice = 0;

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const typicalPrice = (c.high + c.low + c.close) / 3.0;
    const vol = Math.max(1, c.volume);

    cumVolPrice += typicalPrice * vol;
    cumVol += vol;

    const vwap = cumVolPrice / cumVol;
    result.push({
      time: c.open_time as UTCTimestamp,
      value: parseFloat(vwap.toFixed(2)),
    });
  }

  return result;
}

export function calculateRSI(candles: Candle[], period: number = 14): IndicatorPoint[] {
  if (candles.length <= period) return [];

  const result: IndicatorPoint[] = [];
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const change = candles[i].close - candles[i - 1].close;
    if (change > 0) gains += change;
    else losses += Math.abs(change);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  let rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);

  result.push({
    time: candles[period].open_time as UTCTimestamp,
    value: parseFloat(rsi.toFixed(2)),
  });

  for (let i = period + 1; i < candles.length; i++) {
    const change = candles[i].close - candles[i - 1].close;
    const currentGain = change > 0 ? change : 0;
    const currentLoss = change < 0 ? Math.abs(change) : 0;

    avgGain = (avgGain * (period - 1) + currentGain) / period;
    avgLoss = (avgLoss * (period - 1) + currentLoss) / period;

    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + rs);

    result.push({
      time: candles[i].open_time as UTCTimestamp,
      value: parseFloat(rsi.toFixed(2)),
    });
  }

  return result;
}

