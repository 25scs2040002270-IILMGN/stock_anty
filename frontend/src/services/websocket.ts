import { WSMessage } from '../types/market';

type MessageHandler = (msg: WSMessage) => void;
type StatusHandler = (connected: boolean) => void;

export class MarketWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private reconnectTimer: any = null;
  private pingInterval: any = null;
  private isExplicitlyClosed: boolean = false;
  private reconnectDelay: number = 2000;

  constructor(url?: string) {
    this.url = url || (process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://localhost:8000/ws/market');
  }

  public connect(): void {
    if (typeof window === 'undefined') return;
    this.isExplicitlyClosed = false;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectDelay = 2000;
        this.notifyStatus(true);
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const parsed: WSMessage = JSON.parse(event.data);
          this.messageHandlers.forEach((h) => h(parsed));
        } catch (e) {
          // ignore invalid non-JSON messages
        }
      };

      this.ws.onerror = () => {
        // Will trigger onclose
      };

      this.ws.onclose = () => {
        this.notifyStatus(false);
        this.stopHeartbeat();
        if (!this.isExplicitlyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (e) {
      this.scheduleReconnect();
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 10000);
  }

  private stopHeartbeat(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 15000);
      this.connect();
    }, this.reconnectDelay);
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  public onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  public onStatusChange(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  private notifyStatus(connected: boolean): void {
    this.statusHandlers.forEach((h) => h(connected));
  }
}

let clientInstance: MarketWebSocketClient | null = null;

export function getWebSocketClient(): MarketWebSocketClient {
  if (!clientInstance) {
    clientInstance = new MarketWebSocketClient();
  }
  return clientInstance;
}

