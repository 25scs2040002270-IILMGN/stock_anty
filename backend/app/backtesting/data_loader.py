"""MarketPulse AI — Historical Data Loader
Supports validated CSV loading, resampling, Upstox historical candle fetching,
and synthetic test candle generation for HDFCBANK & ICICIBANK.
"""

from typing import Dict, Any, List, Optional
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import httpx
import logging

logger = logging.getLogger(__name__)

ALLOWED_SYMBOLS = ["HDFCBANK", "ICICIBANK"]
INSTRUMENT_KEYS = {
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "ICICIBANK": "NSE_EQ|INE090A01021"
}


def validate_and_parse_csv(file_content: str, symbol: str) -> pd.DataFrame:
    """Parse CSV text into a validated DataFrame of historical candles.
    
    Verifies:
    1. Symbol must be HDFCBANK or ICICIBANK.
    2. Required columns: timestamp, open, high, low, close, volume.
    3. Chronological ascending order, no duplicates, valid price math (high >= low, etc.).
    """
    if symbol not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' not allowed. Only HDFCBANK and ICICIBANK are supported.")
        
    df = pd.read_csv(io.StringIO(file_content))
    # Normalize column names to lowercase
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in CSV.")
            
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    
    # Cast and validate numerical columns
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isnull().any():
            raise ValueError(f"Invalid non-numeric values found in column '{col}'.")
            
    # Check OHLC logical integrity
    invalid_ohlc = (df["high"] < df["low"]) | (df["open"] > df["high"]) | (df["open"] < df["low"]) | (df["close"] > df["high"]) | (df["close"] < df["low"])
    if invalid_ohlc.any():
        raise ValueError("High/Low/Open/Close logical inconsistency detected in CSV rows.")
        
    return df


def resample_candles(df_1m: pd.DataFrame, timeframe_min: int) -> pd.DataFrame:
    """Resample 1-minute OHLCV DataFrame into 5m or 15m OHLCV DataFrame."""
    if df_1m.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        
    df = df_1m.copy()
    df = df.set_index("timestamp")
    
    rule = f"{timeframe_min}min"
    resampled = df.resample(rule, label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna().reset_index()
    
    return resampled


async def fetch_upstox_historical(
    symbol: str,
    interval: str,
    to_date: str,
    from_date: str,
    access_token: str
) -> pd.DataFrame:
    """Fetch historical candles from official Upstox v2 API.
    
    interval: '1minute', '30minute', 'day', 'month' etc.
    """
    if symbol not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' not allowed.")
        
    instrument_key = INSTRUMENT_KEYS.get(symbol)
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Upstox historical API error {resp.status_code}: {resp.text}")
        data = resp.json()
            
    candles = data.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        
    records = []
    for c in candles:
        # Upstox returns [timestamp, open, high, low, close, volume, oi]
        records.append({
            "timestamp": pd.to_datetime(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5])
        })
        
    df = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)
    return df


def generate_synthetic_candles(
    symbol: str = "HDFCBANK",
    n_bars: int = 400,
    start_price: float = 1600.0,
    regime: str = "bullish"
) -> Dict[str, pd.DataFrame]:
    """Generate deterministic synthetic multi-timeframe candle datasets for backtesting tests.
    
    Returns 1m, 5m, and 15m DataFrames aligned chronologically.
    """
    if symbol not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' not allowed.")
        
    np.random.seed(42)
    start_time = datetime(2026, 11, 2, 9, 15, tzinfo=timezone.utc)
    
    prices = [start_price]
    for i in range(1, n_bars):
        if regime == "bullish":
            drift = 0.25
        elif regime == "bearish":
            drift = -0.25
        else:
            drift = 0.0
            
        noise = np.random.normal(0, 1.2)
        next_p = max(100.0, prices[-1] + drift + noise)
        prices.append(next_p)
        
    records = []
    for i in range(n_bars):
        t = start_time + timedelta(minutes=i)
        p = prices[i]
        o = p + np.random.uniform(-0.5, 0.5)
        c = p + np.random.uniform(-0.5, 0.5)
        h = max(o, c) + abs(np.random.normal(0.8, 0.4))
        l = min(o, c) - abs(np.random.normal(0.8, 0.4))
        v = int(abs(np.random.normal(5000, 2000)) + 1000)
        records.append({
            "timestamp": t,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": v
        })
        
    df_1m = pd.DataFrame(records)
    df_5m = resample_candles(df_1m, 5)
    df_15m = resample_candles(df_1m, 15)
    
    return {
        "1m": df_1m,
        "5m": df_5m,
        "15m": df_15m
    }
