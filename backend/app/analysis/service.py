import logging
import asyncio
from typing import Dict, Any, Optional, List
from app.database.connection import get_db
from app.market_data.connection.connection_manager import get_connection_manager
from app.analysis.signals.engine import SignalEngine
from app.analysis.signals.models import SignalResponse
from app.analysis.signals.lifecycle import get_signal_lifecycle_manager
from app.analysis.risk.manager import RiskManager
from app.analysis.indicators.ema import analyze_ema
from app.analysis.indicators.rsi import analyze_rsi
from app.analysis.indicators.vwap import analyze_vwap
from app.analysis.indicators.volume import analyze_volume
from app.analysis.indicators.market_structure import analyze_market_structure
from app.analysis.indicators.support_resistance import analyze_support_resistance
from app.analysis.patterns.candlestick import detect_candlestick_patterns
from app.analysis.liquidity.sweep_detector import analyze_liquidity_and_sweeps
from app.websocket.server import get_broadcaster

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Coordinates quantitative analysis, multi-timeframe indicator computation,
    signal evaluation, and real-time broadcasting.
    """

    def __init__(self) -> None:
        self.db = get_db()
        self.conn_mgr = get_connection_manager()
        self.lifecycle_mgr = get_signal_lifecycle_manager()
        
        # Load risk settings from DB
        risk_dict = self.db.get_risk_settings()
        self.risk_mgr = RiskManager(
            trading_capital=risk_dict.get("trading_capital", 100000.0),
            risk_percentage=risk_dict.get("risk_percentage", 1.0),
            min_rr_ratio=risk_dict.get("max_risk_reward_min", 1.5),
            lot_size=risk_dict.get("lot_size", 1)
        )
        self.engine = SignalEngine(risk_manager=self.risk_mgr)

    def update_risk_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Updates and persists risk parameters."""
        self.db.save_risk_settings(new_settings)
        self.risk_mgr = RiskManager(
            trading_capital=new_settings.get("trading_capital", 100000.0),
            risk_percentage=new_settings.get("risk_percentage", 1.0),
            min_rr_ratio=new_settings.get("max_risk_reward_min", 1.5),
            lot_size=new_settings.get("lot_size", 1)
        )
        self.engine = SignalEngine(risk_manager=self.risk_mgr)
        return self.db.get_risk_settings()

    def get_risk_settings(self) -> Dict[str, Any]:
        return self.db.get_risk_settings()

    async def run_analysis(self, symbol: str) -> SignalResponse:
        """
        Executes end-to-end multi-timeframe analysis for a specific symbol.
        Strictly enforces allowed instruments (HDFCBANK or ICICIBANK).
        """
        sym = symbol.upper()
        if sym not in ("HDFCBANK", "ICICIBANK"):
            raise ValueError(f"CRITICAL VIOLATION: Instrument '{sym}' is not permitted for analysis.")

        # Check data freshness status
        state = self.conn_mgr.current_state.value

        # Fetch completed candles from database
        # 1m: latest 100 candles
        candles_1m = self.db.get_candles(sym, timeframe="1m", limit=100, include_incomplete=False)
        # 5m: latest 60 candles
        candles_5m = self.db.get_candles(sym, timeframe="5m", limit=60, include_incomplete=False)
        # 15m: latest 40 candles
        candles_15m = self.db.get_candles(sym, timeframe="15m", limit=40, include_incomplete=False)

        # Latest tick
        latest_ticks = self.db.get_latest_ticks()
        latest_tick = latest_ticks.get(sym)

        signal = self.engine.generate_signal(
            symbol=sym,
            candles_15m=candles_15m,
            candles_5m=candles_5m,
            candles_1m=candles_1m,
            latest_tick=latest_tick,
            data_freshness_status=state
        )

        # Check invalidation of active signal if price breached stop
        if latest_tick and latest_tick.get("ltp"):
            self.lifecycle_mgr.check_invalidation(sym, float(latest_tick["ltp"]))

        # Check deduplication & lifecycle registration
        latest_1m_time = candles_1m[-1]["open_time"] if candles_1m else 0
        if self.lifecycle_mgr.should_emit_signal(signal, latest_1m_time):
            signal = self.lifecycle_mgr.register_signal(signal)
            # Broadcast new active signal
            try:
                broadcaster = get_broadcaster()
                await broadcaster.broadcast_message("signal", signal.to_dict())
            except Exception as e:
                logger.error(f"Failed to broadcast signal: {e}")

        return signal

    def get_indicators_summary(self, symbol: str) -> Dict[str, Any]:
        """Provides full indicator metrics across all three timeframes."""
        sym = symbol.upper()
        if sym not in ("HDFCBANK", "ICICIBANK"):
            raise ValueError(f"Instrument '{sym}' is not supported.")

        candles_1m = self.db.get_candles(sym, timeframe="1m", limit=50, include_incomplete=False)
        candles_5m = self.db.get_candles(sym, timeframe="5m", limit=50, include_incomplete=False)
        candles_15m = self.db.get_candles(sym, timeframe="15m", limit=50, include_incomplete=False)

        latest_ticks = self.db.get_latest_ticks()
        tick = latest_ticks.get(sym)

        return {
            "symbol": sym,
            "1m": {
                "ema": analyze_ema(candles_1m).to_dict(),
                "rsi": analyze_rsi(candles_1m).to_dict(),
                "volume": analyze_volume(candles_1m).to_dict(),
                "patterns": [p.to_dict() for p in detect_candlestick_patterns(candles_1m)],
                "liquidity_risk": analyze_liquidity_and_sweeps(candles_1m, latest_tick=tick).to_dict()
            },
            "5m": {
                "ema": analyze_ema(candles_5m).to_dict(),
                "vwap": analyze_vwap(candles_5m).to_dict(),
                "volume": analyze_volume(candles_5m).to_dict(),
                "market_structure": analyze_market_structure(candles_5m).to_dict(),
                "support_resistance": analyze_support_resistance(candles_5m).to_dict()
            },
            "15m": {
                "ema": analyze_ema(candles_15m).to_dict(),
                "market_structure": analyze_market_structure(candles_15m).to_dict(),
                "support_resistance": analyze_support_resistance(candles_15m).to_dict()
            }
        }

    async def on_candle_completed(self, candle: Any) -> None:
        """Callback invoked whenever CandleEngine marks a candle complete."""
        try:
            if candle.is_complete and candle.symbol in ("HDFCBANK", "ICICIBANK"):
                await self.run_analysis(candle.symbol)
        except Exception as e:
            logger.error(f"Error executing analysis on completed candle: {e}")


_analysis_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService()
    return _analysis_service

