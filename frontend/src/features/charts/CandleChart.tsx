'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
  CandlestickData,
  HistogramData,
  LineData,
} from 'lightweight-charts';
import { Candle } from '../../types/market';
import { fetchCandles } from '../../services/api';
import { calculateEMA, calculateVWAP, calculateRSI } from '../../utils/chartIndicators';
import { Clock, RefreshCw, Eye, EyeOff } from 'lucide-react';

interface Props {
  symbol: string;
  activeCandle?: Candle | null;
}

type Timeframe = '1m' | '5m' | '15m';

export const CandleChart: React.FC<Props> = ({ symbol, activeCandle }) => {
  const mainChartContainerRef = useRef<HTMLDivElement>(null);
  const rsiChartContainerRef = useRef<HTMLDivElement>(null);

  const mainChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);

  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const ema20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ema50SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [timeframe, setTimeframe] = useState<Timeframe>('1m');
  const [loading, setLoading] = useState<boolean>(true);
  const [candleCount, setCandleCount] = useState<number>(0);
  const [latestRsi, setLatestRsi] = useState<number | null>(null);

  // Overlay toggles
  const [showEMA20, setShowEMA20] = useState<boolean>(true);
  const [showEMA50, setShowEMA50] = useState<boolean>(true);
  const [showVWAP, setShowVWAP] = useState<boolean>(true);
  const [showVolume, setShowVolume] = useState<boolean>(true);
  const [showRSI, setShowRSI] = useState<boolean>(true);

  // Raw candles cache for re-calculating overlays
  const rawCandlesRef = useRef<Candle[]>([]);

  // 1. Initialize Main TradingView Chart
  useEffect(() => {
    if (!mainChartContainerRef.current) return;

    const chart = createChart(mainChartContainerRef.current, {
      layout: {
        background: { color: '#0B0E14' },
        textColor: '#94A3B8',
        fontSize: 12,
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: '#161F30' },
        horzLines: { color: '#161F30' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#38BDF8', width: 1, style: 3 },
        horzLine: { color: '#38BDF8', width: 1, style: 3 },
      },
      timeScale: {
        borderColor: '#1E2638',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#1E2638',
        autoScale: true,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderVisible: false,
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0,
      },
    });

    const ema20Series = chart.addLineSeries({
      color: '#38BDF8',
      lineWidth: 2,
      priceLineVisible: false,
    });

    const ema50Series = chart.addLineSeries({
      color: '#EC4899',
      lineWidth: 2,
      priceLineVisible: false,
    });

    const vwapSeries = chart.addLineSeries({
      color: '#F59E0B',
      lineWidth: 2,
      priceLineVisible: false,
    });

    mainChartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    ema20SeriesRef.current = ema20Series;
    ema50SeriesRef.current = ema50Series;
    vwapSeriesRef.current = vwapSeries;

    const handleResize = () => {
      if (mainChartContainerRef.current && chart) {
        chart.applyOptions({
          width: mainChartContainerRef.current.clientWidth,
          height: mainChartContainerRef.current.clientHeight || 360,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      mainChartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      ema20SeriesRef.current = null;
      ema50SeriesRef.current = null;
      vwapSeriesRef.current = null;
    };
  }, []);

  // 2. Initialize RSI Subchart
  useEffect(() => {
    if (!rsiChartContainerRef.current || !showRSI) return;

    const rsiChart = createChart(rsiChartContainerRef.current, {
      layout: {
        background: { color: '#090D14' },
        textColor: '#64748B',
        fontSize: 10,
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: '#121824' },
        horzLines: { color: '#162032' },
      },
      timeScale: {
        borderColor: '#1E2638',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#1E2638',
        autoScale: false,
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
    });

    const rsiSeries = rsiChart.addLineSeries({
      color: '#A855F7',
      lineWidth: 2,
      priceLineVisible: true,
      autoscaleInfoProvider: () => ({
        priceRange: {
          minValue: 0,
          maxValue: 100,
        },
      }),
    });

    // Add guide levels for 70 and 30
    rsiSeries.createPriceLine({
      price: 70,
      color: '#EF444488',
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: 'OB 70',
    });

    rsiSeries.createPriceLine({
      price: 30,
      color: '#10B98188',
      lineWidth: 1,
      lineStyle: 2,
      axisLabelVisible: true,
      title: 'OS 30',
    });

    rsiSeries.createPriceLine({
      price: 50,
      color: '#47556955',
      lineWidth: 1,
      lineStyle: 1,
      axisLabelVisible: false,
    });

    rsiChartRef.current = rsiChart;
    rsiSeriesRef.current = rsiSeries;

    const handleResize = () => {
      if (rsiChartContainerRef.current && rsiChart) {
        rsiChart.applyOptions({
          width: rsiChartContainerRef.current.clientWidth,
          height: 120,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    // Sync time-scales between main chart and RSI chart
    if (mainChartRef.current) {
      mainChartRef.current.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (range && rsiChart) {
          rsiChart.timeScale().setVisibleRange(range);
        }
      });
      rsiChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (range && mainChartRef.current) {
          mainChartRef.current.timeScale().setVisibleRange(range);
        }
      });
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      rsiChart.remove();
      rsiChartRef.current = null;
      rsiSeriesRef.current = null;
    };
  }, [showRSI]);

  // 3. Load historical candles and compute indicators
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      try {
        const data = await fetchCandles(symbol, timeframe, 300);
        if (cancelled) return;

        rawCandlesRef.current = data || [];
        setCandleCount(data.length);

        if (candleSeriesRef.current && data.length > 0) {
          const chartData: CandlestickData[] = data.map((c) => ({
            time: c.open_time as UTCTimestamp,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }));
          candleSeriesRef.current.setData(chartData);

          // Volume series
          if (volumeSeriesRef.current) {
            const volData: HistogramData[] = data.map((c) => ({
              time: c.open_time as UTCTimestamp,
              value: c.volume,
              color: c.close >= c.open ? '#10B98144' : '#EF444444',
            }));
            volumeSeriesRef.current.setData(showVolume ? volData : []);
          }

          // EMA 20
          if (ema20SeriesRef.current) {
            const ema20 = calculateEMA(data, 20);
            ema20SeriesRef.current.setData(showEMA20 ? (ema20 as LineData[]) : []);
          }

          // EMA 50
          if (ema50SeriesRef.current) {
            const ema50 = calculateEMA(data, 50);
            ema50SeriesRef.current.setData(showEMA50 ? (ema50 as LineData[]) : []);
          }

          // VWAP
          if (vwapSeriesRef.current) {
            const vwap = calculateVWAP(data);
            vwapSeriesRef.current.setData(showVWAP ? (vwap as LineData[]) : []);
          }

          // RSI 14
          const rsi = calculateRSI(data, 14);
          if (rsi.length > 0) {
            setLatestRsi(rsi[rsi.length - 1].value);
          }
          if (rsiSeriesRef.current && showRSI) {
            rsiSeriesRef.current.setData(rsi as LineData[]);
            if (rsiChartRef.current) {
              rsiChartRef.current.timeScale().fitContent();
            }
          }

          if (mainChartRef.current) {
            mainChartRef.current.timeScale().fitContent();
          }
        }
      } catch (err) {
        console.error('Error loading candles:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();

    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe, showEMA20, showEMA50, showVWAP, showVolume, showRSI]);

  // 4. Update on active real-time incoming candle
  useEffect(() => {
    if (!candleSeriesRef.current || !activeCandle) return;
    if (activeCandle.symbol !== symbol || activeCandle.timeframe !== timeframe) return;

    candleSeriesRef.current.update({
      time: activeCandle.open_time as UTCTimestamp,
      open: activeCandle.open,
      high: activeCandle.high,
      low: activeCandle.low,
      close: activeCandle.close,
    });

    if (volumeSeriesRef.current && showVolume) {
      volumeSeriesRef.current.update({
        time: activeCandle.open_time as UTCTimestamp,
        value: activeCandle.volume,
        color: activeCandle.close >= activeCandle.open ? '#10B98144' : '#EF444444',
      });
    }
  }, [activeCandle, symbol, timeframe, showVolume]);

  return (
    <div className="flex flex-col h-full bg-terminal-card border border-terminal-border rounded-xl p-4">
      {/* Top Chart Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-terminal-border/60">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold text-white tracking-wide">
            {symbol} LIVE CHART
          </span>
          <span className="text-[11px] font-mono text-slate-500">
            ({candleCount} candles loaded)
          </span>
          {latestRsi !== null && showRSI && (
            <span
              className={`px-2 py-0.5 text-[10px] font-mono font-semibold rounded border ${
                latestRsi >= 70
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                  : latestRsi <= 30
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-purple-500/10 text-purple-300 border-purple-500/30'
              }`}
            >
              RSI (14): {latestRsi}
            </span>
          )}
        </div>

        {/* Indicator Overlay Toggles */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setShowEMA20(!showEMA20)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-all ${
              showEMA20
                ? 'bg-sky-500/20 text-sky-400 border-sky-500/40'
                : 'text-slate-500 border-terminal-border hover:text-slate-400'
            }`}
          >
            EMA 20
          </button>
          <button
            type="button"
            onClick={() => setShowEMA50(!showEMA50)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-all ${
              showEMA50
                ? 'bg-pink-500/20 text-pink-400 border-pink-500/40'
                : 'text-slate-500 border-terminal-border hover:text-slate-400'
            }`}
          >
            EMA 50
          </button>
          <button
            type="button"
            onClick={() => setShowVWAP(!showVWAP)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-all ${
              showVWAP
                ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                : 'text-slate-500 border-terminal-border hover:text-slate-400'
            }`}
          >
            VWAP
          </button>
          <button
            type="button"
            onClick={() => setShowVolume(!showVolume)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-all ${
              showVolume
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                : 'text-slate-500 border-terminal-border hover:text-slate-400'
            }`}
          >
            VOL
          </button>
          <button
            type="button"
            onClick={() => setShowRSI(!showRSI)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-all ${
              showRSI
                ? 'bg-purple-500/20 text-purple-400 border-purple-500/40'
                : 'text-slate-500 border-terminal-border hover:text-slate-400'
            }`}
          >
            RSI
          </button>

          {/* Timeframe Selectors */}
          <div className="flex items-center gap-1 bg-terminal-bg p-0.5 rounded-lg border border-terminal-border ml-2">
            {(['1m', '5m', '15m'] as Timeframe[]).map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setTimeframe(tf)}
                className={`px-2.5 py-0.5 text-xs font-mono rounded font-medium transition-all ${
                  timeframe === tf
                    ? 'bg-terminal-accent text-slate-900 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                }`}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Candlestick Chart Area */}
      <div className="relative flex-1 min-h-[350px] w-full mt-2">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-terminal-bg/60 backdrop-blur-sm rounded-lg">
            <div className="flex items-center gap-2 text-xs font-mono text-terminal-accent">
              <RefreshCw className="animate-spin" size={16} />
              <span>Loading {symbol} ({timeframe}) candles & indicators...</span>
            </div>
          </div>
        )}

        {candleCount === 0 && !loading && (
          <div className="absolute inset-0 z-0 flex flex-col items-center justify-center text-slate-500 text-xs font-mono p-4 text-center">
            <Clock size={28} className="mb-2 text-slate-600" />
            <p>No historical candles stored yet for {symbol} ({timeframe}).</p>
            <p className="text-[11px] text-slate-600 mt-1">
              Candles build in real-time as market data arrives.
            </p>
          </div>
        )}

        <div ref={mainChartContainerRef} className="w-full h-full" />
      </div>

      {/* RSI Subchart Area */}
      {showRSI && (
        <div className="mt-2 pt-2 border-t border-terminal-border/40">
          <div className="flex items-center justify-between px-1 pb-1">
            <span className="text-[10px] font-mono font-semibold text-purple-400 uppercase tracking-wider">
              RSI (14) Momentum Oscillator
            </span>
            <div className="flex items-center gap-3 text-[10px] font-mono text-slate-500">
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                OB &gt; 70
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                OS &lt; 30
              </span>
            </div>
          </div>
          <div ref={rsiChartContainerRef} className="w-full h-[120px]" />
        </div>
      )}
    </div>
  );
};
