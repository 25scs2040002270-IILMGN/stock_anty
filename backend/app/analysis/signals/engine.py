import time
from typing import Dict, List, Optional, Any, Tuple
from app.analysis.signals.models import SignalResponse, ScoreBreakdown
from app.analysis.signals.scoring import calculate_signal_score
from app.analysis.indicators.ema import analyze_ema, EMAResult
from app.analysis.indicators.rsi import analyze_rsi, RSIResult
from app.analysis.indicators.vwap import analyze_vwap, VWAPResult
from app.analysis.indicators.volume import analyze_volume, VolumeResult
from app.analysis.indicators.market_structure import analyze_market_structure, MarketStructureResult
from app.analysis.indicators.support_resistance import analyze_support_resistance, SupportResistanceResult
from app.analysis.patterns.candlestick import detect_candlestick_patterns, CandlestickPattern
from app.analysis.liquidity.sweep_detector import analyze_liquidity_and_sweeps, LiquidityAnalysisResult
from app.analysis.risk.manager import RiskManager, RiskProfile
from app.utils.timezone import format_ist_datetime, get_ist_now, is_market_session_open


class SignalEngine:
    """
    Multi-Timeframe Rules-Based Technical Signal Engine.
    Coordinates 15m macro trend, 5m setup confirmation, and 1m entry timing
    to produce deterministic BUY, SELL, or WAIT signals.
    """

    def __init__(self, risk_manager: Optional[RiskManager] = None) -> None:
        self.risk_mgr = risk_manager or RiskManager()

    def generate_signal(
        self,
        symbol: str,
        candles_15m: List[Dict[str, Any]],
        candles_5m: List[Dict[str, Any]],
        candles_1m: List[Dict[str, Any]],
        latest_tick: Optional[Dict[str, Any]] = None,
        data_freshness_status: str = "LIVE",
        bypass_market_hours_check: bool = False
    ) -> SignalResponse:
        """
        Executes multi-timeframe quantitative evaluation on completed candles only.
        """
        now_ts = int(time.time())
        now_ist = format_ist_datetime(get_ist_now())

        # 1. Check Data Freshness and Market Session
        is_market_open = True if bypass_market_hours_check else is_market_session_open()
        if not is_market_open:
            return self._build_wait_response(
                symbol=symbol,
                now_ts=now_ts,
                now_ist=now_ist,
                current_price=float(candles_1m[-1]["close"]) if candles_1m else 0.0,
                reason="NSE market is currently closed. Signals generate during active market hours only.",
                data_status=data_freshness_status
            )

        if data_freshness_status in ("STALE", "DISCONNECTED"):
            return self._build_wait_response(
                symbol=symbol,
                now_ts=now_ts,
                now_ist=now_ist,
                current_price=float(candles_1m[-1]["close"]) if candles_1m else 0.0,
                reason=f"Market data feed is {data_freshness_status}. Fresh signals are strictly withheld on stale data.",
                data_status=data_freshness_status
            )

        # 2. Check Minimum Candle Requirements (Completed Candles Only)
        if len(candles_1m) < 15 or len(candles_5m) < 10 or len(candles_15m) < 5:
            return self._build_wait_response(
                symbol=symbol,
                now_ts=now_ts,
                now_ist=now_ist,
                current_price=float(candles_1m[-1]["close"]) if candles_1m else 0.0,
                reason="Accumulating minimum completed candles (1m >= 15, 5m >= 10, 15m >= 5) for reliable multi-timeframe analysis.",
                data_status=data_freshness_status
            )

        current_price = float(candles_1m[-1]["close"])

        # 3. Multi-Timeframe Analytical Calculations
        # 15-Minute: Broader Trend & Major Structure
        struct_15m = analyze_market_structure(candles_15m, order=2)
        ema_15m = analyze_ema(candles_15m, fast_period=20, slow_period=50)

        # Determine 15m trend
        trend_15m = "SIDEWAYS"
        if struct_15m.structure == "BULLISH" and ema_15m.trend_alignment in ("BULLISH", "NEUTRAL"):
            trend_15m = "BULLISH"
        elif struct_15m.structure == "BEARISH" and ema_15m.trend_alignment in ("BEARISH", "NEUTRAL"):
            trend_15m = "BEARISH"
        elif ema_15m.trend_alignment == "BULLISH" and struct_15m.structure != "BEARISH":
            trend_15m = "BULLISH"
        elif ema_15m.trend_alignment == "BEARISH" and struct_15m.structure != "BULLISH":
            trend_15m = "BEARISH"

        # 5-Minute: Setup Confirmation, VWAP, EMA, Volume
        ema_5m = analyze_ema(candles_5m, fast_period=20, slow_period=50)
        vwap_5m = analyze_vwap(candles_5m)
        vol_5m = analyze_volume(candles_5m)
        sr_5m = analyze_support_resistance(candles_5m)
        struct_5m = analyze_market_structure(candles_5m)

        setup_5m = "SIDEWAYS"
        if ema_5m.trend_alignment == "BULLISH" and vwap_5m.is_above_vwap:
            setup_5m = "BULLISH"
        elif ema_5m.trend_alignment == "BEARISH" and not vwap_5m.is_above_vwap:
            setup_5m = "BEARISH"

        # 1-Minute: Entry Timing, RSI, Candlestick Patterns, Liquidity Sweep
        ema_1m = analyze_ema(candles_1m, fast_period=20, slow_period=50)
        rsi_1m = analyze_rsi(candles_1m, period=14)
        vol_1m = analyze_volume(candles_1m)
        patterns_1m = detect_candlestick_patterns(candles_1m)
        liquidity_res = analyze_liquidity_and_sweeps(candles_1m, latest_tick=latest_tick)

        entry_1m = "NEUTRAL"
        if rsi_1m.momentum == "BULLISH" and ema_1m.current_close >= (ema_1m.ema_fast or ema_1m.current_close):
            entry_1m = "BULLISH"
        elif rsi_1m.momentum == "BEARISH" and ema_1m.current_close <= (ema_1m.ema_fast or ema_1m.current_close):
            entry_1m = "BEARISH"

        # Check latest candlestick confirmation
        has_candle_pattern = len(patterns_1m) > 0
        best_pattern: Optional[CandlestickPattern] = patterns_1m[-1] if has_candle_pattern else None
        candle_dir = best_pattern.classification if best_pattern else "NEUTRAL"
        candle_text = best_pattern.explanation if best_pattern else "Standard continuous price action (no single reversal trigger)."

        # 4. Strict Liquidity Check: If high fakeout risk -> force WAIT
        if liquidity_res.is_high_risk:
            return self._build_wait_response(
                symbol=symbol,
                now_ts=now_ts,
                now_ist=now_ist,
                current_price=current_price,
                reason=f"Liquidity Sweep / Fakeout Risk is {liquidity_res.fakeout_risk_level}: {liquidity_res.reason}",
                data_status=data_freshness_status,
                liquidity_res=liquidity_res,
                trend_15m_exp=struct_15m.explanation,
                setup_5m_exp=vwap_5m.explanation,
                entry_1m_exp=rsi_1m.explanation
            )

        # 5. Evaluate Candidate BUY
        score_buy = calculate_signal_score(
            target_direction="BUY",
            trend_15m=trend_15m,
            setup_5m=setup_5m,
            entry_1m=entry_1m,
            ema_align=ema_5m.trend_alignment,
            has_ema_cross=ema_5m.is_bullish_cross or ema_1m.is_bullish_cross,
            vwap_align="BULLISH" if vwap_5m.is_above_vwap else "BEARISH",
            has_vwap_cross=vwap_5m.is_bullish_cross,
            rsi_momentum=rsi_1m.momentum,
            has_rsi_divergence=(rsi_1m.divergence == "BULLISH_DIVERGENCE"),
            is_rsi_extreme=rsi_1m.is_overbought,
            volume_confirmed=vol_5m.is_confirmed,
            is_volume_expansion=vol_5m.is_expansion or vol_1m.is_expansion,
            structure=struct_5m.structure,
            is_at_key_level=sr_5m.is_at_support or sr_5m.is_retest,
            has_candlestick_pat=has_candle_pattern,
            candlestick_dir=candle_dir,
            fakeout_risk_level=liquidity_res.fakeout_risk_level
        )

        # 6. Evaluate Candidate SELL
        score_sell = calculate_signal_score(
            target_direction="SELL",
            trend_15m=trend_15m,
            setup_5m=setup_5m,
            entry_1m=entry_1m,
            ema_align=ema_5m.trend_alignment,
            has_ema_cross=ema_5m.is_bearish_cross or ema_1m.is_bearish_cross,
            vwap_align="BULLISH" if vwap_5m.is_above_vwap else "BEARISH",
            has_vwap_cross=vwap_5m.is_bearish_cross,
            rsi_momentum=rsi_1m.momentum,
            has_rsi_divergence=(rsi_1m.divergence == "BEARISH_DIVERGENCE"),
            is_rsi_extreme=rsi_1m.is_oversold,
            volume_confirmed=vol_5m.is_confirmed,
            is_volume_expansion=vol_5m.is_expansion or vol_1m.is_expansion,
            structure=struct_5m.structure,
            is_at_key_level=sr_5m.is_at_resistance or sr_5m.is_rejection,
            has_candlestick_pat=has_candle_pattern,
            candlestick_dir=candle_dir,
            fakeout_risk_level=liquidity_res.fakeout_risk_level
        )

        # 7. Rules Threshold & Filter Verification
        # Strict BUY Verification
        is_buy_eligible = (
            score_buy.total_score >= 70 and
            trend_15m in ("BULLISH", "SIDEWAYS") and
            setup_5m == "BULLISH" and
            vwap_5m.is_above_vwap and
            not rsi_1m.is_overbought and
            vol_5m.relative_volume >= 0.75
        )

        # Strict SELL Verification
        is_sell_eligible = (
            score_sell.total_score >= 70 and
            trend_15m in ("BEARISH", "SIDEWAYS") and
            setup_5m == "BEARISH" and
            not vwap_5m.is_above_vwap and
            not rsi_1m.is_oversold and
            vol_5m.relative_volume >= 0.75
        )

        # 8. Construct Final Signal (BUY, SELL, or WAIT)
        if is_buy_eligible and not is_sell_eligible:
            risk_prof = self.risk_mgr.calculate_trade_risk(
                symbol=symbol,
                direction="BUY",
                current_price=current_price,
                structure_stop=sr_5m.nearest_support or struct_5m.recent_swing_low,
                structure_target=sr_5m.nearest_resistance
            )
            if not risk_prof.is_valid_rr:
                return self._build_wait_response(
                    symbol=symbol,
                    now_ts=now_ts,
                    now_ist=now_ist,
                    current_price=current_price,
                    reason=f"Insufficient Risk-to-Reward ratio (1:{risk_prof.risk_reward_ratio:.2f} < minimum required 1:1.50).",
                    data_status=data_freshness_status
                )

            return SignalResponse(
                symbol=symbol,
                direction="BUY",
                signal_timestamp=now_ts,
                signal_datetime_ist=now_ist,
                current_market_price=current_price,
                entry_zone={"low": risk_prof.entry_zone_low, "center": risk_prof.entry_price, "high": risk_prof.entry_zone_high},
                stop_loss=risk_prof.stop_loss,
                target=risk_prof.target,
                risk_reward_ratio=risk_prof.risk_reward_ratio,
                expected_validity_minutes=15,
                scoring_breakdown=score_buy,
                trend_15m_explanation=f"15m macro structure is {trend_15m}. {struct_15m.explanation}",
                setup_5m_explanation=f"5m setup is {setup_5m}. Price above session VWAP (₹{vwap_5m.vwap:.2f}) and {ema_5m.explanation}",
                entry_1m_explanation=f"1m timing confirmation: {entry_1m}. {rsi_1m.explanation}",
                ema_explanation=f"5m: {ema_5m.explanation} | 1m: {ema_1m.explanation}",
                rsi_explanation=rsi_1m.explanation,
                vwap_explanation=vwap_5m.explanation,
                volume_confirmation=f"5m RVOL: {vol_5m.relative_volume:.2f}x. {vol_5m.explanation}",
                support_resistance_explanation=sr_5m.explanation,
                candlestick_confirmation=candle_text,
                liquidity_sweep_risk=f"{liquidity_res.fakeout_risk_level}: {liquidity_res.reason}",
                invalidation_condition=f"Close below stop loss ₹{risk_prof.stop_loss:.2f} or 5m close below VWAP ₹{vwap_5m.vwap:.2f}.",
                data_freshness_status=data_freshness_status,
                position_sizing=risk_prof.to_dict()
            )

        elif is_sell_eligible and not is_buy_eligible:
            risk_prof = self.risk_mgr.calculate_trade_risk(
                symbol=symbol,
                direction="SELL",
                current_price=current_price,
                structure_stop=sr_5m.nearest_resistance or struct_5m.recent_swing_high,
                structure_target=sr_5m.nearest_support
            )
            if not risk_prof.is_valid_rr:
                return self._build_wait_response(
                    symbol=symbol,
                    now_ts=now_ts,
                    now_ist=now_ist,
                    current_price=current_price,
                    reason=f"Insufficient Risk-to-Reward ratio (1:{risk_prof.risk_reward_ratio:.2f} < minimum required 1:1.50).",
                    data_status=data_freshness_status
                )

            return SignalResponse(
                symbol=symbol,
                direction="SELL",
                signal_timestamp=now_ts,
                signal_datetime_ist=now_ist,
                current_market_price=current_price,
                entry_zone={"low": risk_prof.entry_zone_low, "center": risk_prof.entry_price, "high": risk_prof.entry_zone_high},
                stop_loss=risk_prof.stop_loss,
                target=risk_prof.target,
                risk_reward_ratio=risk_prof.risk_reward_ratio,
                expected_validity_minutes=15,
                scoring_breakdown=score_sell,
                trend_15m_explanation=f"15m macro structure is {trend_15m}. {struct_15m.explanation}",
                setup_5m_explanation=f"5m setup is {setup_5m}. Price below session VWAP (₹{vwap_5m.vwap:.2f}) and {ema_5m.explanation}",
                entry_1m_explanation=f"1m timing confirmation: {entry_1m}. {rsi_1m.explanation}",
                ema_explanation=f"5m: {ema_5m.explanation} | 1m: {ema_1m.explanation}",
                rsi_explanation=rsi_1m.explanation,
                vwap_explanation=vwap_5m.explanation,
                volume_confirmation=f"5m RVOL: {vol_5m.relative_volume:.2f}x. {vol_5m.explanation}",
                support_resistance_explanation=sr_5m.explanation,
                candlestick_confirmation=candle_text,
                liquidity_sweep_risk=f"{liquidity_res.fakeout_risk_level}: {liquidity_res.reason}",
                invalidation_condition=f"Close above stop loss ₹{risk_prof.stop_loss:.2f} or 5m close above VWAP ₹{vwap_5m.vwap:.2f}.",
                data_freshness_status=data_freshness_status,
                position_sizing=risk_prof.to_dict()
            )

        else:
            # Default to WAIT
            reasons = []
            if score_buy.total_score < 70 and score_sell.total_score < 70:
                reasons.append(f"Insufficient technical score alignment (BUY: {score_buy.total_score}/100, SELL: {score_sell.total_score}/100; min 70 required)")
            if trend_15m != setup_5m and trend_15m != "SIDEWAYS" and setup_5m != "SIDEWAYS":
                reasons.append(f"Timeframe conflict: 15m trend ({trend_15m}) disagrees with 5m setup ({setup_5m})")
            if vol_5m.relative_volume < 0.75:
                reasons.append(f"Subdued volume participation (5m RVOL {vol_5m.relative_volume:.2f}x)")
            if not reasons:
                reasons.append("Price consolidating between key levels without directional conviction.")

            return self._build_wait_response(
                symbol=symbol,
                now_ts=now_ts,
                now_ist=now_ist,
                current_price=current_price,
                reason=" | ".join(reasons),
                data_status=data_freshness_status,
                liquidity_res=liquidity_res,
                trend_15m_exp=struct_15m.explanation,
                setup_5m_exp=vwap_5m.explanation,
                entry_1m_exp=rsi_1m.explanation
            )

    def _build_wait_response(
        self,
        symbol: str,
        now_ts: int,
        now_ist: str,
        current_price: float,
        reason: str,
        data_status: str,
        liquidity_res: Optional[LiquidityAnalysisResult] = None,
        trend_15m_exp: str = "Market structure in equilibrium or awaiting candles.",
        setup_5m_exp: str = "Setup neutral or consolidating.",
        entry_1m_exp: str = "Waiting for high-probability entry trigger."
    ) -> SignalResponse:
        """Helper to build a structured WAIT response adhering to Section 9."""
        zero_score = ScoreBreakdown(
            total_score=0,
            max_score=100,
            trend_15m_score=0,
            setup_5m_score=0,
            entry_1m_score=0,
            ema_score=0,
            vwap_score=0,
            rsi_score=0,
            volume_score=0,
            structure_score=0,
            sr_score=0,
            candlestick_score=0,
            liquidity_penalty=0,
            notes=[reason]
        )

        return SignalResponse(
            symbol=symbol,
            direction="WAIT",
            signal_timestamp=now_ts,
            signal_datetime_ist=now_ist,
            current_market_price=round(current_price, 2),
            entry_zone={"low": round(current_price, 2), "center": round(current_price, 2), "high": round(current_price, 2)},
            stop_loss=0.0,
            target=0.0,
            risk_reward_ratio=0.0,
            expected_validity_minutes=10,
            scoring_breakdown=zero_score,
            trend_15m_explanation=trend_15m_exp,
            setup_5m_explanation=setup_5m_exp,
            entry_1m_explanation=entry_1m_exp,
            ema_explanation="Indicators neutral or awaiting directional clarity.",
            rsi_explanation="RSI within normal range or unconfirmed.",
            vwap_explanation="No confirmed directional break away from VWAP.",
            volume_confirmation="Volume unconfirmed or balanced between buyers and sellers.",
            support_resistance_explanation="Awaiting clear reaction at verified support or resistance level.",
            candlestick_confirmation="No decisive single or multi-candle confirmation.",
            liquidity_sweep_risk=liquidity_res.reason if liquidity_res else "Low fakeout risk / normal liquidity.",
            invalidation_condition="Fresh directional breakout and multi-timeframe alignment.",
            data_freshness_status=data_status,
            position_sizing=None
        )

