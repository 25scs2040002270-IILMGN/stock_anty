"""MarketPulse AI — Backtesting Engine
Executes chronological walk-forward historical simulation with strict zero look-ahead bias,
train/validation/test splits, conservative intraday execution, and Indian NSE equity fee calculations.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timezone

from app.analysis.signals.engine import SignalEngine
from app.analysis.risk.manager import RiskManager
from app.analysis.signals.outcome_evaluator import calculate_nse_charges
from app.database.models import TradeRecord, BacktestRunRecord

ALLOWED_SYMBOLS = ["HDFCBANK", "ICICIBANK"]


class BacktestEngine:
    def __init__(
        self,
        symbol: str,
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 0.01,
        slippage_pct: float = 0.0005,
        min_rr_ratio: float = 1.5,
        max_horizon_bars: int = 15,
        train_ratio: float = 0.60,
        val_ratio: float = 0.20,
        test_ratio: float = 0.20
    ):
        if symbol not in ALLOWED_SYMBOLS:
            raise ValueError(f"Symbol '{symbol}' not permitted. Backtesting only supports HDFCBANK and ICICIBANK.")
            
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.slippage_pct = slippage_pct
        self.min_rr_ratio = min_rr_ratio
        self.max_horizon_bars = max_horizon_bars
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        
        risk_pct = risk_per_trade_pct * 100.0 if risk_per_trade_pct <= 0.1 else risk_per_trade_pct
        self.risk_mgr = RiskManager(
            trading_capital=initial_capital,
            risk_percentage=risk_pct,
            min_rr_ratio=min_rr_ratio
        )
        self.signal_engine = SignalEngine(risk_manager=self.risk_mgr)

    def run(
        self,
        df_1m: pd.DataFrame,
        df_5m: Optional[pd.DataFrame] = None,
        df_15m: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """Execute the chronological walk-forward backtest."""
        if df_1m.empty or len(df_1m) < 40:
            raise ValueError("Insufficient candle history for backtest (minimum 40 1-minute bars required).")
            
        # Ensure DataFrames are sorted
        df_1m = df_1m.sort_values("timestamp").reset_index(drop=True)
        if df_5m is None or df_5m.empty:
            from app.backtesting.data_loader import resample_candles
            df_5m = resample_candles(df_1m, 5)
        else:
            df_5m = df_5m.sort_values("timestamp").reset_index(drop=True)
            
        if df_15m is None or df_15m.empty:
            from app.backtesting.data_loader import resample_candles
            df_15m = resample_candles(df_1m, 15)
        else:
            df_15m = df_15m.sort_values("timestamp").reset_index(drop=True)

        n_total_bars = len(df_1m)
        train_cutoff = int(n_total_bars * self.train_ratio)
        val_cutoff = int(n_total_bars * (self.train_ratio + self.val_ratio))
        
        trades: List[TradeRecord] = []
        signal_counts = {"BUY": 0, "SELL": 0, "WAIT": 0}
        
        # Warmup index: need at least 15 1m, 10 5m, 5 15m
        warmup_idx = 30
        
        current_idx = warmup_idx
        backtest_id = str(uuid.uuid4())
        
        while current_idx < n_total_bars - 1:
            curr_bar = df_1m.iloc[current_idx]
            curr_time = curr_bar["timestamp"]
            
            # Slice strictly completed candles prior to current_idx (NO LOOK-AHEAD)
            past_1m = df_1m.iloc[:current_idx].to_dict(orient="records")
            past_5m = df_5m[df_5m["timestamp"] + pd.Timedelta(minutes=5) <= curr_time].to_dict(orient="records")
            past_15m = df_15m[df_15m["timestamp"] + pd.Timedelta(minutes=15) <= curr_time].to_dict(orient="records")
            
            if len(past_1m) < 15 or len(past_5m) < 10 or len(past_15m) < 5:
                current_idx += 1
                continue
                
            sig = self.signal_engine.generate_signal(
                symbol=self.symbol,
                candles_15m=past_15m,
                candles_5m=past_5m,
                candles_1m=past_1m,
                data_freshness_status="LIVE",
                bypass_market_hours_check=True
            )
            
            direction = sig.direction.upper()
            signal_counts[direction] = signal_counts.get(direction, 0) + 1
            
            if direction not in ("BUY", "SELL"):
                current_idx += 1
                continue
                
            # Determine split partition
            if current_idx < train_cutoff:
                split_name = "TRAIN"
            elif current_idx < val_cutoff:
                split_name = "VALIDATION"
            else:
                split_name = "TEST"
                
            # Determine market regime from 15m trend & liquidity risk
            regime = "SIDEWAYS"
            if "BULLISH" in sig.trend_15m_explanation.upper():
                regime = "TRENDING_BULLISH"
            elif "BEARISH" in sig.trend_15m_explanation.upper():
                regime = "TRENDING_BEARISH"
            elif "HIGH" in sig.liquidity_sweep_risk.upper() or "ELEVATED" in sig.liquidity_sweep_risk.upper():
                regime = "VOLATILE"
                
            # Trade entry: next candle open (current_idx bar open) with slippage
            raw_entry = float(curr_bar["open"])
            if direction == "BUY":
                entry_price = raw_entry * (1.0 + self.slippage_pct)
            else:
                entry_price = raw_entry * (1.0 - self.slippage_pct)
                
            entry_time = str(curr_time)
            sl = sig.stop_loss
            tgt = sig.target
            qty = 10
            if sig.position_sizing and sig.position_sizing.get("suggested_shares"):
                qty = max(1, int(sig.position_sizing["suggested_shares"]))
            elif abs(entry_price - sl) > 0.1:
                qty = max(1, int((self.initial_capital * self.risk_per_trade_pct) / abs(entry_price - sl)))
            
            # Simulate forward resolution over subsequent candles
            exit_price = entry_price
            exit_time = entry_time
            exit_reason = "EXPIRED"
            duration_bars = 0
            
            eval_idx = current_idx
            while eval_idx < n_total_bars and duration_bars < self.max_horizon_bars:
                eval_bar = df_1m.iloc[eval_idx]
                eval_high = float(eval_bar["high"])
                eval_low = float(eval_bar["low"])
                eval_close = float(eval_bar["close"])
                eval_time = str(eval_bar["timestamp"])
                duration_bars += 1
                
                if direction == "BUY":
                    sl_hit = (eval_low <= sl)
                    tgt_hit = (eval_high >= tgt)
                    
                    if sl_hit and tgt_hit:
                        # Conservative rule: stop loss hit first
                        exit_price = sl * (1.0 - self.slippage_pct)
                        exit_time = eval_time
                        exit_reason = "HIT_STOP_LOSS"
                        break
                    elif sl_hit:
                        exit_price = sl * (1.0 - self.slippage_pct)
                        exit_time = eval_time
                        exit_reason = "HIT_STOP_LOSS"
                        break
                    elif tgt_hit:
                        exit_price = tgt * (1.0 - self.slippage_pct)
                        exit_time = eval_time
                        exit_reason = "HIT_TARGET"
                        break
                else:  # SELL
                    sl_hit = (eval_high >= sl)
                    tgt_hit = (eval_low <= tgt)
                    
                    if sl_hit and tgt_hit:
                        exit_price = sl * (1.0 + self.slippage_pct)
                        exit_time = eval_time
                        exit_reason = "HIT_STOP_LOSS"
                        break
                    elif sl_hit:
                        exit_price = sl * (1.0 + self.slippage_pct)
                        exit_time = eval_time
                        exit_reason = "HIT_STOP_LOSS"
                        break
                    elif tgt_hit:
                        exit_price = tgt * (1.0 + self.slippage_pct)
                        exit_time = eval_time
                        exit_reason = "HIT_TARGET"
                        break
                        
                if duration_bars >= self.max_horizon_bars:
                    exit_price = eval_close
                    exit_time = eval_time
                    exit_reason = "EXPIRED"
                    break
                    
                eval_idx += 1
                
            # Compute PnL & NSE fees
            if direction == "BUY":
                gross_pnl = (exit_price - entry_price) * qty
                buy_val = entry_price * qty
                sell_val = exit_price * qty
            else:
                gross_pnl = (entry_price - exit_price) * qty
                buy_val = exit_price * qty
                sell_val = entry_price * qty
                
            charges_info = calculate_nse_charges(buy_val, sell_val)
            charges = charges_info["total_charges"]
            net_pnl = gross_pnl - charges
            pnl_pct = (net_pnl / (entry_price * qty)) * 100 if entry_price * qty > 0 else 0.0
            
            trade = TradeRecord(
                trade_id=str(uuid.uuid4())[:8],
                symbol=self.symbol,
                side=direction,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=round(entry_price, 2),
                exit_price=round(exit_price, 2),
                quantity=qty,
                stop_loss=round(sl, 2),
                target=round(tgt, 2),
                gross_pnl=round(gross_pnl, 2),
                charges=charges,
                net_pnl=round(net_pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                exit_reason=exit_reason,
                duration_minutes=duration_bars,
                split=split_name,
                regime=regime
            )
            trades.append(trade)
            
            # Step index to evaluation exit to avoid redundant re-triggers on the same candle sequence
            current_idx = max(current_idx + 1, eval_idx + 1)
            
        # Compute performance summary
        metrics = self._calculate_metrics(trades, signal_counts)
        metrics["backtest_id"] = backtest_id
        metrics["symbol"] = self.symbol
        metrics["start_date"] = str(df_1m.iloc[0]["timestamp"])
        metrics["end_date"] = str(df_1m.iloc[-1]["timestamp"])
        metrics["total_candles"] = n_total_bars
        metrics["trades"] = [t.model_dump() for t in trades]
        
        return metrics

    def _calculate_metrics(self, trades: List[TradeRecord], signal_counts: Dict[str, int]) -> Dict[str, Any]:
        """Compute statistical backtesting metrics across all trades and splits."""
        total_trades = len(trades)
        buy_trades = [t for t in trades if t.side == "BUY"]
        sell_trades = [t for t in trades if t.side == "SELL"]
        
        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl <= 0]
        
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0
        
        gross_profit = sum(t.gross_pnl for t in winning_trades)
        gross_loss = sum(abs(t.gross_pnl) for t in losing_trades)
        total_charges = sum(t.charges for t in trades)
        net_profit = sum(t.net_pnl for t in trades)
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
        expectancy = (net_profit / total_trades) if total_trades > 0 else 0.0
        
        # Max Drawdown calculation using running equity curve
        equity = self.initial_capital
        peak = equity
        max_dd_val = 0.0
        max_dd_pct = 0.0
        equity_curve = [{"time": "START", "equity": round(equity, 2)}]
        
        for t in trades:
            equity += t.net_pnl
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
            if dd > max_dd_val:
                max_dd_val = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
            equity_curve.append({
                "time": t.exit_time,
                "equity": round(equity, 2),
                "pnl": t.net_pnl
            })
            
        avg_holding_time = (sum(t.duration_minutes for t in trades) / total_trades) if total_trades > 0 else 0.0
        
        # Split performance breakdown
        splits_perf = {}
        for s_name in ["TRAIN", "VALIDATION", "TEST"]:
            s_trades = [t for t in trades if t.split == s_name]
            s_wins = [t for t in s_trades if t.net_pnl > 0]
            s_net = sum(t.net_pnl for t in s_trades)
            splits_perf[s_name.lower()] = {
                "trades": len(s_trades),
                "win_rate": round(len(s_wins) / len(s_trades) * 100.0, 1) if s_trades else 0.0,
                "net_pnl": round(s_net, 2),
                "profit_factor": round(
                    sum(t.gross_pnl for t in s_wins) / max(0.01, sum(abs(t.gross_pnl) for t in s_trades if t.net_pnl <= 0)),
                    2
                ) if s_trades else 1.0
            }
            
        # Market regime performance breakdown
        regime_perf = {}
        for r_name in ["TRENDING_BULLISH", "TRENDING_BEARISH", "SIDEWAYS", "VOLATILE"]:
            r_trades = [t for t in trades if t.regime == r_name]
            r_wins = [t for t in r_trades if t.net_pnl > 0]
            r_net = sum(t.net_pnl for t in r_trades)
            regime_perf[r_name.lower()] = {
                "trades": len(r_trades),
                "win_rate": round(len(r_wins) / len(r_trades) * 100.0, 1) if r_trades else 0.0,
                "net_pnl": round(r_net, 2)
            }
            
        return {
            "total_signals": signal_counts.get("BUY", 0) + signal_counts.get("SELL", 0) + signal_counts.get("WAIT", 0),
            "signal_counts": signal_counts,
            "total_trades": total_trades,
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "total_charges": round(total_charges, 2),
            "net_profit": round(net_profit, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "max_drawdown": round(max_dd_val, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "avg_holding_time_minutes": round(avg_holding_time, 1),
            "initial_capital": round(self.initial_capital, 2),
            "final_equity": round(equity, 2),
            "return_pct": round(((equity - self.initial_capital) / self.initial_capital) * 100.0, 2),
            "splits": splits_perf,
            "regimes": regime_perf,
            "equity_curve": equity_curve
        }
