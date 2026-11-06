'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { MarketTick, Candle, ConnectionStatus, WSMessage, HealthStatus } from '../types/market';
import { getWebSocketClient } from '../services/websocket';
import { fetchHealth, fetchMarketStatus, fetchLatestTicks } from '../services/api';

export function useMarketFeed() {
  const [ticks, setTicks] = useState<Record<string, MarketTick>>({});
  const [activeCandles, setActiveCandles] = useState<Record<string, Candle>>({});
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isWsConnected, setIsWsConnected] = useState<boolean>(false);
  const [lastMessageTime, setLastMessageTime] = useState<number | null>(null);

  // Reference for stable handler callbacks
  const ticksRef = useRef(ticks);
  ticksRef.current = ticks;

  // Poll health and status periodically as backup
  const refreshStatus = useCallback(async () => {
    try {
      const [h, s, latest] = await Promise.allSettled([
        fetchHealth(),
        fetchMarketStatus(),
        fetchLatestTicks()
      ]);

      if (h.status === 'fulfilled') setHealth(h.value);
      if (s.status === 'fulfilled') setConnectionStatus(s.value);
      if (latest.status === 'fulfilled' && latest.value) {
        setTicks((prev) => ({
          ...prev,
          ...latest.value
        }));
      }
    } catch (e) {
      // offline or server restarting
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 10000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  // Connect to WebSocket
  useEffect(() => {
    const wsClient = getWebSocketClient();
    wsClient.connect();

    const unsubStatus = wsClient.onStatusChange((connected) => {
      setIsWsConnected(connected);
    });

    const unsubMsg = wsClient.onMessage((msg: WSMessage) => {
      setLastMessageTime(Date.now());

      if (msg.type === 'tick' && msg.data) {
        const tick = msg.data as MarketTick;
        setTicks((prev) => ({
          ...prev,
          [tick.symbol]: tick
        }));
      } else if (msg.type === 'candle' && msg.data) {
        const candle = msg.data as Candle;
        const key = `${candle.symbol}_${candle.timeframe}`;
        setActiveCandles((prev) => ({
          ...prev,
          [key]: candle
        }));
      } else if (msg.type === 'status' && msg.data) {
        setConnectionStatus(msg.data as ConnectionStatus);
      }
    });

    return () => {
      unsubStatus();
      unsubMsg();
    };
  }, []);

  return {
    ticks,
    activeCandles,
    connectionStatus,
    health,
    isWsConnected,
    lastMessageTime,
    refreshStatus
  };
}

