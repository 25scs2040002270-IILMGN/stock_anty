"""MarketPulse AI — Backtesting & Evaluated Signals API Routes
Provides endpoints for running backtests, viewing historical performance,
uploading CSV candle datasets, and retrieving daily risk and signal summaries.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import json
import logging

from app.database.connection import get_db, DatabaseManager
from app.backtesting.engine import BacktestEngine
from app.backtesting.data_loader import (
    validate_and_parse_csv,
    generate_synthetic_candles,
    ALLOWED_SYMBOLS
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["backtesting", "signals-analysis"])


class BacktestRunRequest(BaseModel):
    symbol: str = Field(..., description="Instrument symbol (HDFCBANK or ICICIBANK)")
    initial_capital: float = Field(100000.0, description="Starting capital in INR")
    risk_per_trade_pct: float = Field(0.01, description="Risk per trade (0.01 = 1%)")
    slippage_pct: float = Field(0.0005, description="Slippage percentage (0.0005 = 0.05%)")
    min_rr_ratio: float = Field(1.5, description="Minimum risk/reward ratio")
    source: str = Field("synthetic", description="'synthetic' or 'database'")
    synthetic_bars: int = Field(350, description="Number of bars if using synthetic generation")
    synthetic_regime: str = Field("bullish", description="'bullish', 'bearish', or 'sideways'")


class CSVBacktestRequest(BaseModel):
    symbol: str = Field(..., description="Instrument symbol (HDFCBANK or ICICIBANK)")
    csv_content: str = Field(..., description="Raw CSV string with timestamp,open,high,low,close,volume")
    initial_capital: float = Field(100000.0, description="Starting capital in INR")
    risk_per_trade_pct: float = Field(0.01, description="Risk per trade (0.01 = 1%)")
    slippage_pct: float = Field(0.0005, description="Slippage percentage")


@router.post("/backtest/run")
async def run_backtest(
    req: BacktestRunRequest,
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """Execute a backtest run on historical or synthetic candle data."""
    symbol = req.symbol.upper()
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{symbol}' not permitted. Only HDFCBANK and ICICIBANK are supported."
        )

    # 1. Acquire candle dataset
    if req.source == "database":
        candles_1m_data = db.get_candles(symbol, timeframe="1m", limit=500, include_incomplete=False)
        candles_5m_data = db.get_candles(symbol, timeframe="5m", limit=200, include_incomplete=False)
        candles_15m_data = db.get_candles(symbol, timeframe="15m", limit=100, include_incomplete=False)
        
        if len(candles_1m_data) < 40:
            # Fallback to synthetic if database has insufficient live candles yet
            candles_dict = generate_synthetic_candles(
                symbol=symbol,
                n_bars=req.synthetic_bars,
                regime=req.synthetic_regime
            )
            df_1m = candles_dict["1m"]
            df_5m = candles_dict["5m"]
            df_15m = candles_dict["15m"]
        else:
            import pandas as pd
            df_1m = pd.DataFrame(candles_1m_data).rename(columns={"open_datetime_ist": "timestamp"})
            df_5m = pd.DataFrame(candles_5m_data).rename(columns={"open_datetime_ist": "timestamp"})
            df_15m = pd.DataFrame(candles_15m_data).rename(columns={"open_datetime_ist": "timestamp"})
    else:
        candles_dict = generate_synthetic_candles(
            symbol=symbol,
            n_bars=req.synthetic_bars,
            regime=req.synthetic_regime
        )
        df_1m = candles_dict["1m"]
        df_5m = candles_dict["5m"]
        df_15m = candles_dict["15m"]

    # 2. Instantiate and execute backtest engine
    engine = BacktestEngine(
        symbol=symbol,
        initial_capital=req.initial_capital,
        risk_per_trade_pct=req.risk_per_trade_pct,
        slippage_pct=req.slippage_pct,
        min_rr_ratio=req.min_rr_ratio
    )
    
    try:
        report = engine.run(df_1m=df_1m, df_5m=df_5m, df_15m=df_15m)
    except Exception as e:
        logger.error(f"Backtest execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest error: {str(e)}")

    # 3. Persist run to database
    backtest_data = {
        "symbol": symbol,
        "timeframe": "1m+5m+15m",
        "start_date": report["start_date"],
        "end_date": report["end_date"],
        "total_signals": report["total_signals"],
        "buy_signals": report["signal_counts"].get("BUY", 0),
        "sell_signals": report["signal_counts"].get("SELL", 0),
        "wait_signals": report["signal_counts"].get("WAIT", 0),
        "total_trades": report["total_trades"],
        "win_rate": report["win_rate"],
        "profit_factor": report["profit_factor"],
        "max_drawdown_pct": report["max_drawdown_pct"],
        "net_pnl": report["net_profit"],
        "summary": {k: v for k, v in report.items() if k != "trades"},
        "trades": report["trades"]
    }
    saved_id = db.save_backtest(backtest_data)
    report["id"] = saved_id
    
    return {
        "status": "success",
        "data": report
    }


@router.get("/backtest/results/{backtest_id}")
async def get_backtest_result(
    backtest_id: int,
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """Retrieve details and trades of a previous backtest run."""
    result = db.get_backtest(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest report not found.")
    return {
        "status": "success",
        "data": result
    }


@router.get("/backtest/recent")
async def list_recent_backtests(
    limit: int = Query(10, ge=1, le=50),
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """List recent backtest summaries."""
    runs = db.get_recent_backtests(limit=limit)
    return {
        "status": "success",
        "data": runs
    }


@router.post("/backtest/upload-csv")
async def upload_and_backtest_csv(
    req: CSVBacktestRequest,
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """Upload custom historical 1-minute candle CSV and run backtest."""
    sym = req.symbol.upper()
    if sym not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol '{sym}' not permitted. Only HDFCBANK and ICICIBANK supported.")
        
    try:
        df_1m = validate_and_parse_csv(req.csv_content, sym)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV validation failed: {str(e)}")
        
    engine = BacktestEngine(
        symbol=sym,
        initial_capital=req.initial_capital,
        risk_per_trade_pct=req.risk_per_trade_pct,
        slippage_pct=req.slippage_pct
    )
    
    report = engine.run(df_1m=df_1m)
    
    backtest_data = {
        "symbol": sym,
        "timeframe": "1m (resampled 5m/15m)",
        "start_date": report["start_date"],
        "end_date": report["end_date"],
        "total_signals": report["total_signals"],
        "buy_signals": report["signal_counts"].get("BUY", 0),
        "sell_signals": report["signal_counts"].get("SELL", 0),
        "wait_signals": report["signal_counts"].get("WAIT", 0),
        "total_trades": report["total_trades"],
        "win_rate": report["win_rate"],
        "profit_factor": report["profit_factor"],
        "max_drawdown_pct": report["max_drawdown_pct"],
        "net_pnl": report["net_profit"],
        "summary": {k: v for k, v in report.items() if k != "trades"},
        "trades": report["trades"]
    }
    saved_id = db.save_backtest(backtest_data)
    report["id"] = saved_id
    
    return {
        "status": "success",
        "data": report
    }


@router.get("/signals/daily-summary")
async def get_daily_risk_and_signals_summary(
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """Returns today's aggregate signals summary, hypothetical win/loss counts, and risk limits."""
    summary = db.get_signals_daily_summary()
    return {
        "status": "success",
        "data": summary
    }


@router.get("/signals/evaluated-history")
async def get_evaluated_signals_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """Returns historical signals with evaluated trade outcomes (HIT_TARGET, HIT_STOP_LOSS, EXPIRED, etc.)."""
    history = db.get_evaluated_signals_history(symbol=symbol, limit=limit)
    return {
        "status": "success",
        "data": history
    }
