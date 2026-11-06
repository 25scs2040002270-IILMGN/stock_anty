/**
 * MarketPulse AI — Web Audio API Synthetic Chime & Browser Notification System.
 * Generates pure synthesizer chimes without external audio asset dependencies.
 */

class NotificationService {
  private audioCtx: AudioContext | null = null;
  private soundEnabled: boolean = true;
  private browserNotificationsEnabled: boolean = false;

  constructor() {
    if (typeof window !== 'undefined') {
      const savedSound = localStorage.getItem('marketpulse_sound_enabled');
      if (savedSound !== null) {
        this.soundEnabled = savedSound === 'true';
      }

      const savedNotify = localStorage.getItem('marketpulse_browser_notify_enabled');
      if (savedNotify !== null) {
        this.browserNotificationsEnabled = savedNotify === 'true';
      }
    }
  }

  private getAudioContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
      }
    }
    if (this.audioCtx && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
    return this.audioCtx;
  }

  /**
   * Plays a pleasant dual-tone synthesizer chime (880 Hz -> 1320 Hz)
   */
  public playSignalChime(isBullish: boolean = true): void {
    if (!this.soundEnabled) return;

    try {
      const ctx = this.getAudioContext();
      if (!ctx) return;

      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      if (isBullish) {
        // Upward melody: A5 (880Hz) -> E6 (1318.5Hz)
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(1318.5, now + 0.15);
      } else {
        // Downward melody: E6 (1318.5Hz) -> A5 (880Hz)
        osc.frequency.setValueAtTime(1318.5, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.15);
      }

      // Envelope: quick attack and smooth decay
      gain.gain.setValueAtTime(0.001, now);
      gain.gain.linearRampToValueAtTime(0.25, now + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.45);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.5);
    } catch (e) {
      console.warn('Audio chime playback failed:', e);
    }
  }

  /**
   * Requests HTML5 Desktop Notification permission
   */
  public async requestNotificationPermission(): Promise<boolean> {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      const granted = permission === 'granted';
      this.browserNotificationsEnabled = granted;
      localStorage.setItem('marketpulse_browser_notify_enabled', granted.toString());
      return granted;
    } catch (e) {
      console.warn('Error requesting notification permission:', e);
      return false;
    }
  }

  /**
   * Dispatches desktop notification if permitted
   */
  public notifySignal(symbol: string, direction: string, price: number, score: number): void {
    if (!this.browserNotificationsEnabled) return;
    if (typeof window === 'undefined' || !('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;

    try {
      new Notification(`MarketPulse AI: ${direction} ${symbol}`, {
        body: `Price: ₹${price.toFixed(2)} | Score: ${score}/100\nRules-based analytical suggestion.`,
        icon: '/favicon.ico',
        tag: `signal-${symbol}-${direction}-${Date.now()}`
      });
    } catch (e) {
      console.warn('Desktop notification dispatch failed:', e);
    }
  }

  public setSoundEnabled(val: boolean): void {
    this.soundEnabled = val;
    if (typeof window !== 'undefined') {
      localStorage.setItem('marketpulse_sound_enabled', val.toString());
    }
  }

  public isSoundEnabled(): boolean {
    return this.soundEnabled;
  }

  public isBrowserNotificationEnabled(): boolean {
    return this.browserNotificationsEnabled;
  }
}

export const notifications = new NotificationService();

