import time
import logging
from typing import Dict, List, Optional, Any
from app.database.connection import get_db
from app.database.models import SignalRecord
from app.analysis.signals.models import SignalResponse

logger = logging.getLogger(__name__)


class SignalLifecycleManager:
    """
    Supervises signal lifecycle:
    - Deduplicates alerts so incoming ticks do not generate repetitive signals
    - Manages active signals in memory and SQLite
    - Enforces automatic expiration after validity period (~15 mins)
    - Checks invalidation conditions (stop loss breach or opposing candle close)
    - Persists historical signals and invalidation reasons to SQLite
    """

    def __init__(self) -> None:
        self.db = get_db()
        # Active signals: symbol -> SignalResponse
        self.active_signals: Dict[str, SignalResponse] = {}
        # Signature of last emitted signal: symbol -> (direction, rounded_price, last_candle_time)
        self.last_signal_signatures: Dict[str, tuple] = {}

    def should_emit_signal(self, candidate: SignalResponse, latest_candle_open_time: int) -> bool:
        """
        Deduplication rule:
        Returns True only if:
        1. Direction is BUY or SELL, and
        2. No active signal with the same direction was generated on this same candle or price level.
        WAIT signals are returned on demand but do not create duplicate active alerts.
        """
        sym = candidate.symbol
        if candidate.direction == "WAIT":
            # If an active BUY/SELL exists, check if it should be invalidated
            return False

        sig = (candidate.direction, round(candidate.current_market_price, 1), latest_candle_open_time)
        if self.last_signal_signatures.get(sym) == sig:
            logger.debug(f"Duplicate signal prevented for {sym} at {sig}")
            return False

        # If there is already an active signal in the same direction, don't duplicate
        active = self.active_signals.get(sym)
        if active and active.direction == candidate.direction:
            # Same direction active: verify if 15 mins has passed
            now = int(time.time())
            age_min = (now - active.signal_timestamp) / 60.0
            if age_min < active.expected_validity_minutes:
                logger.debug(f"Active {active.direction} signal for {sym} still valid ({age_min:.1f}m ago). Skipping duplicate.")
                return False

        self.last_signal_signatures[sym] = sig
        return True

    def register_signal(self, signal: SignalResponse) -> SignalResponse:
        """Saves a new active signal to memory and database."""
        sym = signal.symbol

        # Expire any prior active signal for this symbol
        self.check_and_expire_signals(sym)

        if signal.direction in ("BUY", "SELL"):
            record = SignalRecord(
                symbol=sym,
                direction=signal.direction,
                signal_timestamp=signal.signal_timestamp,
                signal_datetime_ist=signal.signal_datetime_ist,
                current_market_price=signal.current_market_price,
                entry_price=signal.entry_zone.get("center"),
                entry_zone_low=signal.entry_zone.get("low"),
                entry_zone_high=signal.entry_zone.get("high"),
                stop_loss=signal.stop_loss,
                target=signal.target,
                risk_reward_ratio=signal.risk_reward_ratio,
                score=signal.scoring_breakdown.total_score,
                status="ACTIVE",
                invalidation_reason=None,
                payload=signal.to_dict()
            )
            saved_id = self.db.save_signal(record)
            signal.id = saved_id
            self.active_signals[sym] = signal
            logger.info(f"Registered new ACTIVE {signal.direction} signal #{saved_id} for {sym} at ₹{signal.current_market_price:.2f}")

        return signal

    def check_and_expire_signals(self, symbol: Optional[str] = None) -> None:
        """Expires active signals whose validity period has elapsed."""
        now = int(time.time())
        symbols = [symbol] if symbol else list(self.active_signals.keys())

        for sym in symbols:
            active = self.active_signals.get(sym)
            if not active:
                continue

            elapsed_minutes = (now - active.signal_timestamp) / 60.0
            if elapsed_minutes >= active.expected_validity_minutes:
                logger.info(f"Signal #{active.id} for {sym} expired after {elapsed_minutes:.1f} minutes.")
                if active.id:
                    self.db.update_signal_status(
                        active.id,
                        status="EXPIRED",
                        invalidation_reason=f"Validity horizon of {active.expected_validity_minutes} minutes elapsed."
                    )
                del self.active_signals[sym]

    def check_invalidation(self, symbol: str, current_price: float) -> Optional[str]:
        """
        Checks whether active signal stop-loss has been breached.
        """
        active = self.active_signals.get(symbol)
        if not active or active.direction not in ("BUY", "SELL"):
            return None

        # Check BUY stop-loss
        if active.direction == "BUY" and current_price <= active.stop_loss:
            reason = f"Price touched stop loss ₹{active.stop_loss:.2f} (current price ₹{current_price:.2f})."
            self._invalidate_active(symbol, reason)
            return reason

        # Check SELL stop-loss
        if active.direction == "SELL" and current_price >= active.stop_loss:
            reason = f"Price touched stop loss ₹{active.stop_loss:.2f} (current price ₹{current_price:.2f})."
            self._invalidate_active(symbol, reason)
            return reason

        return None

    def _invalidate_active(self, symbol: str, reason: str) -> None:
        active = self.active_signals.get(symbol)
        if active and active.id:
            logger.info(f"Invalidating active {active.direction} signal #{active.id} for {symbol}: {reason}")
            self.db.update_signal_status(active.id, status="INVALIDATED", invalidation_reason=reason)
            del self.active_signals[symbol]


_lifecycle_instance: Optional[SignalLifecycleManager] = None


def get_signal_lifecycle_manager() -> SignalLifecycleManager:
    global _lifecycle_instance
    if _lifecycle_instance is None:
        _lifecycle_instance = SignalLifecycleManager()
    return _lifecycle_instance

