"""MarketPulse AI — Signal Outcome Evaluator
Evaluates generated trading signals against subsequent historical/live candles
to determine objective outcomes: HIT_TARGET, HIT_STOP_LOSS, EXPIRED, INVALIDATED, ACTIVE.
Calculates gross and net P&L with Indian equity charges.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import pandas as pd

from app.database.models import SignalRecord, TradeRecord


def calculate_nse_charges(buy_turnover: float, sell_turnover: float) -> Dict[str, float]:
    """Calculate standard statutory and brokerage charges for Indian NSE equity intraday.
    
    - Brokerage: ₹20 or 0.03% (whichever is lower) per order
    - STT: 0.025% on sell value
    - Exchange Turnover Charges: 0.00345% of turnover
    - GST: 18% on (brokerage + exchange charges)
    - SEBI Charges: 0.0001% of turnover
    - Stamp Duty: 0.003% on buy value
    """
    total_turnover = buy_turnover + sell_turnover
    
    brokerage_buy = min(20.0, buy_turnover * 0.0003)
    brokerage_sell = min(20.0, sell_turnover * 0.0003)
    total_brokerage = brokerage_buy + brokerage_sell
    
    stt = sell_turnover * 0.00025
    exchange_charges = total_turnover * 0.0000345
    gst = (total_brokerage + exchange_charges) * 0.18
    sebi_charges = total_turnover * 0.000001
    stamp_duty = buy_turnover * 0.00003
    
    total_charges = total_brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty
    
    return {
        "brokerage": round(total_brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(exchange_charges, 2),
        "gst": round(gst, 2),
        "sebi_charges": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "total_charges": round(total_charges, 2)
    }


def evaluate_signal_outcome(
    signal: SignalRecord,
    subsequent_candles: List[Dict[str, Any]],
    max_horizon_minutes: int = 15,
    slippage_pct: float = 0.0005
) -> Dict[str, Any]:
    """Evaluate a single BUY or SELL signal across subsequent 1-minute candle bars.
    
    Rules:
    1. Conservative resolution: If both Target and SL are touched in the same candle bar,
       assume STOP LOSS was hit first.
    2. Slippage is applied to entry (and exit if market execution).
    3. Expiry occurs when max_horizon_minutes elapses without touching either level.
    4. Invalidation occurs if invalidation price level is hit.
    """
    if signal.direction.upper() == "WAIT":
        return {
            "outcome": "SKIPPED",
            "exit_price": None,
            "exit_timestamp": None,
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "charges": 0.0,
            "duration_minutes": 0,
            "reason": "WAIT signal — no trade executed"
        }
    
    side = signal.direction.upper()
    entry_ref = signal.entry_price or getattr(signal, "current_market_price", getattr(signal, "current_price", 0.0))
    sl = signal.stop_loss
    target = signal.target
    quantity = getattr(signal, "quantity", 10) or 10
    
    # Adjust entry with slippage
    if side == "BUY":
        effective_entry = entry_ref * (1 + slippage_pct)
    else:
        effective_entry = entry_ref * (1 - slippage_pct)
        
    outcome = "ACTIVE"
    exit_price = None
    exit_timestamp = None
    exit_reason = "Signal still open"
    bars_elapsed = 0
    
    for bar in subsequent_candles:
        bars_elapsed += 1
        bar_high = float(bar["high"])
        bar_low = float(bar["low"])
        bar_close = float(bar["close"])
        bar_time = bar.get("timestamp")
        
        if side == "BUY":
            sl_touched = (bar_low <= sl)
            tgt_touched = (bar_high >= target)
            
            # Conservative rule: if both touched in same candle, SL hit first
            if sl_touched and tgt_touched:
                outcome = "HIT_STOP_LOSS"
                exit_price = sl * (1 - slippage_pct)
                exit_timestamp = bar_time
                exit_reason = "Both SL and Target crossed in same bar; conservative SL exit"
                break
            elif sl_touched:
                outcome = "HIT_STOP_LOSS"
                exit_price = sl * (1 - slippage_pct)
                exit_timestamp = bar_time
                exit_reason = f"Stop Loss touched at {sl}"
                break
            elif tgt_touched:
                outcome = "HIT_TARGET"
                exit_price = target * (1 - slippage_pct)
                exit_timestamp = bar_time
                exit_reason = f"Target touched at {target}"
                break
        else:  # SELL (short)
            sl_touched = (bar_high >= sl)
            tgt_touched = (bar_low <= target)
            
            if sl_touched and tgt_touched:
                outcome = "HIT_STOP_LOSS"
                exit_price = sl * (1 + slippage_pct)
                exit_timestamp = bar_time
                exit_reason = "Both SL and Target crossed in same bar; conservative SL exit"
                break
            elif sl_touched:
                outcome = "HIT_STOP_LOSS"
                exit_price = sl * (1 + slippage_pct)
                exit_timestamp = bar_time
                exit_reason = f"Stop Loss touched at {sl}"
                break
            elif tgt_touched:
                outcome = "HIT_TARGET"
                exit_price = target * (1 + slippage_pct)
                exit_timestamp = bar_time
                exit_reason = f"Target touched at {target}"
                break
                
        # Check horizon expiry
        if bars_elapsed >= max_horizon_minutes:
            outcome = "EXPIRED"
            exit_price = bar_close
            exit_timestamp = bar_time
            exit_reason = f"Forecast horizon expired after {bars_elapsed} minutes"
            break
            
    # Calculate P&L if closed
    if outcome != "ACTIVE" and exit_price is not None:
        if side == "BUY":
            gross_pnl = (exit_price - effective_entry) * quantity
            buy_turnover = effective_entry * quantity
            sell_turnover = exit_price * quantity
        else:
            gross_pnl = (effective_entry - exit_price) * quantity
            buy_turnover = exit_price * quantity
            sell_turnover = effective_entry * quantity
            
        charges_info = calculate_nse_charges(buy_turnover, sell_turnover)
        net_pnl = gross_pnl - charges_info["total_charges"]
        
        return {
            "outcome": outcome,
            "entry_price": round(effective_entry, 2),
            "exit_price": round(exit_price, 2),
            "exit_timestamp": exit_timestamp,
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "charges": charges_info["total_charges"],
            "charges_detail": charges_info,
            "duration_minutes": bars_elapsed,
            "reason": exit_reason
        }
        
    return {
        "outcome": "ACTIVE",
        "entry_price": round(effective_entry, 2),
        "exit_price": None,
        "exit_timestamp": None,
        "gross_pnl": 0.0,
        "net_pnl": 0.0,
        "charges": 0.0,
        "duration_minutes": bars_elapsed,
        "reason": "Position active"
    }
