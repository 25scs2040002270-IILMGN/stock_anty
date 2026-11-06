import sqlite3
import json
import time
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager

from app.config.settings import settings
from app.utils.timezone import get_ist_now, format_ist_datetime
from app.database.models import InstrumentRecord, CandleRecord, ConnectionLogRecord, SignalRecord, RiskSettings


class DatabaseManager:
    """
    Manages SQLite database connections, schema migrations, and queries.
    Uses journal_mode=DELETE with deterministic connection closing
    to prevent file locking on Windows/OneDrive environments.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    @contextmanager
    def connection(self):
        """Yields an active SQLite connection inside a transaction and guarantees closure."""
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Creates tables, constraints, and indexes if they do not exist."""
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        try:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA journal_mode=DELETE;")
            conn.executescript("""
            -- Instruments table
            CREATE TABLE IF NOT EXISTS instruments (
                instrument_key TEXT PRIMARY KEY,
                trading_symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                segment TEXT NOT NULL,
                instrument_type TEXT NOT NULL,
                tick_size REAL DEFAULT 0.05,
                lot_size INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                resolved_at TEXT NOT NULL,
                metadata_json TEXT
            );

            -- Market Ticks table
            CREATE TABLE IF NOT EXISTS market_ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                instrument_key TEXT NOT NULL,
                exchange TEXT NOT NULL,
                ltp REAL NOT NULL,
                exchange_timestamp INTEGER NOT NULL,
                exchange_datetime_ist TEXT NOT NULL,
                last_traded_quantity INTEGER DEFAULT 0,
                cumulative_volume INTEGER DEFAULT 0,
                ohlc_open REAL,
                ohlc_high REAL,
                ohlc_low REAL,
                ohlc_close REAL,
                bids_json TEXT,
                asks_json TEXT,
                received_at INTEGER NOT NULL,
                provider TEXT NOT NULL,
                data_status TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time 
                ON market_ticks (symbol, exchange_timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_ticks_key_time 
                ON market_ticks (instrument_key, exchange_timestamp DESC);

            -- Candles table (1m, 5m, 15m)
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_key TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open_time INTEGER NOT NULL,
                close_time INTEGER NOT NULL,
                open_datetime_ist TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                is_complete INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                CONSTRAINT uq_candle_bucket UNIQUE (instrument_key, timeframe, open_time)
            );

            CREATE INDEX IF NOT EXISTS idx_candles_key_tf_time 
                ON candles (instrument_key, timeframe, open_time DESC);
            CREATE INDEX IF NOT EXISTS idx_candles_sym_tf_time 
                ON candles (symbol, timeframe, open_time DESC);

            -- Connection Logs table
            CREATE TABLE IF NOT EXISTS connection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                state TEXT NOT NULL,
                message TEXT NOT NULL,
                details_json TEXT,
                timestamp INTEGER NOT NULL,
                datetime_ist TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_connection_logs_time 
                ON connection_logs (timestamp DESC);

            -- Application Settings table
            CREATE TABLE IF NOT EXISTS application_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            -- Signals table (BUY, SELL, WAIT)
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                signal_timestamp INTEGER NOT NULL,
                signal_datetime_ist TEXT NOT NULL,
                current_market_price REAL NOT NULL,
                entry_price REAL,
                entry_zone_low REAL,
                entry_zone_high REAL,
                stop_loss REAL,
                target REAL,
                risk_reward_ratio REAL,
                score INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                invalidation_reason TEXT,
                outcome TEXT DEFAULT 'ACTIVE',
                exit_price REAL,
                exit_timestamp INTEGER,
                pnl_gross REAL,
                pnl_net REAL,
                payload_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_signals_sym_time 
                ON signals (symbol, signal_timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_signals_status 
                ON signals (status);

            -- Historical Backtesting runs table
            CREATE TABLE IF NOT EXISTS backtests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                total_signals INTEGER NOT NULL,
                buy_signals INTEGER NOT NULL,
                sell_signals INTEGER NOT NULL,
                wait_signals INTEGER NOT NULL,
                total_trades INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL NOT NULL,
                max_drawdown_pct REAL NOT NULL,
                net_pnl REAL NOT NULL,
                summary_json TEXT NOT NULL,
                trades_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_backtests_sym 
                ON backtests (symbol, created_at DESC);
            """)

            # Ensure new columns exist on signals table if migrated from earlier schema
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(signals)")
            existing_cols = {col[1] for col in cursor.fetchall()}
            for col_name, col_type in [
                ("outcome", "TEXT DEFAULT 'ACTIVE'"),
                ("exit_price", "REAL"),
                ("exit_timestamp", "INTEGER"),
                ("pnl_gross", "REAL"),
                ("pnl_net", "REAL")
            ]:
                if col_name not in existing_cols:
                    try:
                        conn.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_type};")
                    except Exception:
                        pass

            conn.commit()
        finally:
            conn.close()

    # ----------------------------------------------------
    # Instruments Methods
    # ----------------------------------------------------
    def save_instrument(self, record: InstrumentRecord) -> None:
        metadata_str = json.dumps(record.metadata or {})
        with self.connection() as conn:
            conn.execute("""
            INSERT INTO instruments (
                instrument_key, trading_symbol, exchange, segment,
                instrument_type, tick_size, lot_size, is_active, resolved_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_key) DO UPDATE SET
                trading_symbol=excluded.trading_symbol,
                exchange=excluded.exchange,
                segment=excluded.segment,
                instrument_type=excluded.instrument_type,
                tick_size=excluded.tick_size,
                lot_size=excluded.lot_size,
                is_active=excluded.is_active,
                resolved_at=excluded.resolved_at,
                metadata_json=excluded.metadata_json;
            """, (
                record.instrument_key, record.trading_symbol, record.exchange,
                record.segment, record.instrument_type, record.tick_size,
                record.lot_size, 1 if record.is_active else 0,
                record.resolved_at or format_ist_datetime(get_ist_now()),
                metadata_str
            ))

    def get_instruments(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            query = "SELECT * FROM instruments"
            if active_only:
                query += " WHERE is_active = 1"
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("metadata_json"):
                    try:
                        item["metadata"] = json.loads(item["metadata_json"])
                    except Exception:
                        item["metadata"] = {}
                else:
                    item["metadata"] = {}
                result.append(item)
            return result

    def get_instrument_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.execute("SELECT * FROM instruments WHERE trading_symbol = ? LIMIT 1", (symbol.upper(),))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("metadata_json"):
                try:
                    item["metadata"] = json.loads(item["metadata_json"])
                except Exception:
                    item["metadata"] = {}
            return item

    # ----------------------------------------------------
    # Market Ticks Methods
    # ----------------------------------------------------
    def save_tick(self, tick_dict: Dict[str, Any]) -> int:
        now_ms = int(time.time() * 1000)
        ex_time_ms = tick_dict.get("exchange_timestamp", now_ms)
        ex_time_ist = format_ist_datetime(ex_time_ms)

        bids = json.dumps(tick_dict.get("bids", []))
        asks = json.dumps(tick_dict.get("asks", []))
        ohlc = tick_dict.get("ohlc", {}) or {}

        with self.connection() as conn:
            cursor = conn.execute("""
            INSERT INTO market_ticks (
                symbol, instrument_key, exchange, ltp,
                exchange_timestamp, exchange_datetime_ist,
                last_traded_quantity, cumulative_volume,
                ohlc_open, ohlc_high, ohlc_low, ohlc_close,
                bids_json, asks_json, received_at, provider, data_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tick_dict["symbol"],
                tick_dict["instrument_key"],
                tick_dict.get("exchange", "NSE_EQ"),
                tick_dict["ltp"],
                ex_time_ms,
                ex_time_ist,
                tick_dict.get("last_traded_quantity", 0),
                tick_dict.get("cumulative_volume", 0),
                ohlc.get("open"),
                ohlc.get("high"),
                ohlc.get("low"),
                ohlc.get("close"),
                bids,
                asks,
                tick_dict.get("received_at", now_ms),
                tick_dict.get("provider", "UPSTOX"),
                tick_dict.get("data_status", "LIVE")
            ))
            return cursor.lastrowid

    def get_latest_ticks(self) -> Dict[str, Dict[str, Any]]:
        with self.connection() as conn:
            result = {}
            for sym in settings.instruments_list:
                cursor = conn.execute("""
                SELECT * FROM market_ticks 
                WHERE symbol = ? 
                ORDER BY exchange_timestamp DESC 
                LIMIT 1
                """, (sym,))
                row = cursor.fetchone()
                if row:
                    item = dict(row)
                    if item.get("bids_json"):
                        item["bids"] = json.loads(item["bids_json"])
                    if item.get("asks_json"):
                        item["asks"] = json.loads(item["asks_json"])
                    result[sym] = item
            return result

    # ----------------------------------------------------
    # Candles Methods
    # ----------------------------------------------------
    def save_or_update_candle(self, candle: CandleRecord) -> None:
        now_sec = int(time.time())
        created_at = candle.created_at or now_sec
        updated_at = now_sec

        with self.connection() as conn:
            conn.execute("""
            INSERT INTO candles (
                instrument_key, symbol, timeframe, open_time, close_time,
                open_datetime_ist, open, high, low, close, volume,
                is_complete, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_key, timeframe, open_time) DO UPDATE SET
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                is_complete = excluded.is_complete,
                updated_at = excluded.updated_at;
            """, (
                candle.instrument_key,
                candle.symbol,
                candle.timeframe,
                candle.open_time,
                candle.close_time,
                candle.open_datetime_ist,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
                1 if candle.is_complete else 0,
                created_at,
                updated_at
            ))

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 200,
        include_incomplete: bool = True
    ) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            query = """
            SELECT * FROM candles 
            WHERE symbol = ? AND timeframe = ?
            """
            params: List[Any] = [symbol.upper(), timeframe]
            if not include_incomplete:
                query += " AND is_complete = 1"
            query += " ORDER BY open_time ASC"
            
            wrapped_query = f"""
            SELECT * FROM (
                {query.replace('ASC', 'DESC')} LIMIT ?
            ) ORDER BY open_time ASC;
            """
            params.append(limit)
            cursor = conn.execute(wrapped_query, params)
            return [dict(r) for r in cursor.fetchall()]

    # ----------------------------------------------------
    # Connection Logs Methods
    # ----------------------------------------------------
    def log_connection_event(
        self,
        provider: str,
        state: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        now_ms = int(time.time() * 1000)
        now_ist = format_ist_datetime(now_ms)
        details_str = json.dumps(details or {})

        with self.connection() as conn:
            conn.execute("""
            INSERT INTO connection_logs (provider, state, message, details_json, timestamp, datetime_ist)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (provider, state, message, details_str, now_ms, now_ist))

    def get_connection_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.execute("""
            SELECT * FROM connection_logs ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            res = []
            for r in rows:
                item = dict(r)
                if item.get("details_json"):
                    try:
                        item["details"] = json.loads(item["details_json"])
                    except Exception:
                        item["details"] = {}
                else:
                    item["details"] = {}
                res.append(item)
            return res

    # ----------------------------------------------------
    # Application Settings Methods
    # ----------------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.connection() as conn:
            cursor = conn.execute("SELECT value FROM application_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row["value"]
            return default

    def set_setting(self, key: str, value: str) -> None:
        now_sec = int(time.time())
        with self.connection() as conn:
            conn.execute("""
            INSERT INTO application_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at;
            """, (key, value, now_sec))

    # ----------------------------------------------------
    # Signals Methods
    # ----------------------------------------------------
    def save_signal(self, signal: "SignalRecord") -> int:
        now_sec = int(time.time())
        created_at = signal.created_at or now_sec
        updated_at = now_sec
        payload_str = json.dumps(signal.payload or {})

        with self.connection() as conn:
            cursor = conn.execute("""
            INSERT INTO signals (
                symbol, direction, signal_timestamp, signal_datetime_ist,
                current_market_price, entry_price, entry_zone_low, entry_zone_high,
                stop_loss, target, risk_reward_ratio, score, status,
                invalidation_reason, outcome, exit_price, exit_timestamp, pnl_gross, pnl_net,
                payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.symbol,
                signal.direction,
                signal.signal_timestamp,
                signal.signal_datetime_ist,
                signal.current_market_price,
                signal.entry_price,
                signal.entry_zone_low,
                signal.entry_zone_high,
                signal.stop_loss,
                signal.target,
                signal.risk_reward_ratio,
                signal.score,
                signal.status,
                signal.invalidation_reason,
                signal.outcome or "ACTIVE",
                signal.exit_price,
                signal.exit_timestamp,
                signal.pnl_gross,
                signal.pnl_net,
                payload_str,
                created_at,
                updated_at
            ))
            return cursor.lastrowid

    def update_signal_status(self, signal_id: int, status: str, invalidation_reason: Optional[str] = None) -> None:
        now_sec = int(time.time())
        with self.connection() as conn:
            conn.execute("""
            UPDATE signals 
            SET status = ?, invalidation_reason = ?, updated_at = ?
            WHERE id = ?
            """, (status, invalidation_reason, now_sec, signal_id))

    def update_signal_outcome(
        self,
        signal_id: int,
        outcome: str,
        exit_price: float,
        exit_timestamp: int,
        pnl_gross: float,
        pnl_net: float
    ) -> None:
        now_sec = int(time.time())
        with self.connection() as conn:
            conn.execute("""
            UPDATE signals 
            SET outcome = ?, exit_price = ?, exit_timestamp = ?, pnl_gross = ?, pnl_net = ?, updated_at = ?
            WHERE id = ?
            """, (outcome, exit_price, exit_timestamp, pnl_gross, pnl_net, now_sec, signal_id))

    def get_signals_daily_summary(self) -> Dict[str, Any]:
        """Calculates today's analytical signal summary in IST."""
        now_ts = int(time.time())
        # Start of today in IST: (now_ts + 19800) // 86400 * 86400 - 19800
        start_of_today_ts = ((now_ts + 19800) // 86400) * 86400 - 19800

        with self.connection() as conn:
            cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_signals,
                SUM(CASE WHEN direction = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN direction = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                SUM(CASE WHEN direction = 'WAIT' THEN 1 ELSE 0 END) as wait_count,
                SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active_count,
                SUM(CASE WHEN status = 'EXPIRED' THEN 1 ELSE 0 END) as expired_count,
                SUM(CASE WHEN status = 'INVALIDATED' THEN 1 ELSE 0 END) as invalidated_count,
                SUM(CASE WHEN outcome = 'HIT_TARGET' THEN 1 ELSE 0 END) as hit_target_count,
                SUM(CASE WHEN outcome = 'HIT_STOP_LOSS' THEN 1 ELSE 0 END) as hit_sl_count
            FROM signals
            WHERE signal_timestamp >= ?
            """, (start_of_today_ts,))
            row = dict(cursor.fetchone() or {})
            risk = self.get_risk_settings()
            return {
                "date_ist": format_ist_datetime(now_ts)[:10],
                "total_signals_today": row.get("total_signals") or 0,
                "buy_count": row.get("buy_count") or 0,
                "sell_count": row.get("sell_count") or 0,
                "wait_count": row.get("wait_count") or 0,
                "active_signals": row.get("active_count") or 0,
                "expired_signals": row.get("expired_count") or 0,
                "invalidated_signals": row.get("invalidated_count") or 0,
                "hypothetical_target_hits": row.get("hit_target_count") or 0,
                "hypothetical_stop_losses": row.get("hit_sl_count") or 0,
                "trading_capital": risk.get("trading_capital", 100000.0),
                "risk_percentage": risk.get("risk_percentage", 1.0),
                "max_monetary_risk_per_trade": (risk.get("trading_capital", 100000.0) * risk.get("risk_percentage", 1.0)) / 100.0
            }

    def get_evaluated_signals_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            query = "SELECT * FROM signals"
            params: List[Any] = []
            if symbol:
                query += " WHERE symbol = ?"
                params.append(symbol.upper())
            query += " ORDER BY signal_timestamp DESC LIMIT ?"
            params.append(limit)
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("payload_json"):
                    try:
                        item["payload"] = json.loads(item["payload_json"])
                    except Exception:
                        item["payload"] = {}
                result.append(item)
            return result

    # ----------------------------------------------------
    # Backtesting Methods
    # ----------------------------------------------------
    def save_backtest(self, backtest_data: Dict[str, Any]) -> int:
        now_sec = int(time.time())
        summary_str = json.dumps(backtest_data.get("summary", {}))
        trades_str = json.dumps(backtest_data.get("trades", []))

        with self.connection() as conn:
            cursor = conn.execute("""
            INSERT INTO backtests (
                symbol, timeframe, start_date, end_date, total_signals,
                buy_signals, sell_signals, wait_signals, total_trades,
                win_rate, profit_factor, max_drawdown_pct, net_pnl,
                summary_json, trades_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                backtest_data["symbol"],
                backtest_data["timeframe"],
                backtest_data["start_date"],
                backtest_data["end_date"],
                backtest_data.get("total_signals", 0),
                backtest_data.get("buy_signals", 0),
                backtest_data.get("sell_signals", 0),
                backtest_data.get("wait_signals", 0),
                backtest_data.get("total_trades", 0),
                backtest_data.get("win_rate", 0.0),
                backtest_data.get("profit_factor", 0.0),
                backtest_data.get("max_drawdown_pct", 0.0),
                backtest_data.get("net_pnl", 0.0),
                summary_str,
                trades_str,
                now_sec
            ))
            return cursor.lastrowid

    def get_backtest(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.execute("SELECT * FROM backtests WHERE id = ?", (backtest_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("summary_json"):
                item["summary"] = json.loads(item["summary_json"])
            if item.get("trades_json"):
                item["trades"] = json.loads(item["trades_json"])
            return item

    def get_recent_backtests(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.execute("SELECT id, symbol, timeframe, start_date, end_date, total_trades, win_rate, profit_factor, net_pnl, created_at FROM backtests ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_active_signals(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            query = "SELECT * FROM signals WHERE status = 'ACTIVE'"
            params: List[Any] = []
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())
            query += " ORDER BY signal_timestamp DESC"
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("payload_json"):
                    try:
                        item["payload"] = json.loads(item["payload_json"])
                    except Exception:
                        item["payload"] = {}
                result.append(item)
            return result

    def get_signals_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            query = "SELECT * FROM signals"
            params: List[Any] = []
            if symbol:
                query += " WHERE symbol = ?"
                params.append(symbol.upper())
            query += " ORDER BY signal_timestamp DESC LIMIT ?"
            params.append(limit)
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("payload_json"):
                    try:
                        item["payload"] = json.loads(item["payload_json"])
                    except Exception:
                        item["payload"] = {}
                result.append(item)
            return result

    # ----------------------------------------------------
    # Risk Settings Methods
    # ----------------------------------------------------
    def get_risk_settings(self) -> Dict[str, Any]:
        val = self.get_setting("risk_settings")
        if val:
            try:
                return json.loads(val)
            except Exception:
                pass
        return {
            "trading_capital": 100000.0,
            "risk_percentage": 1.0,
            "max_risk_reward_min": 1.5,
            "lot_size": 1
        }

    def save_risk_settings(self, settings_dict: Dict[str, Any]) -> None:
        self.set_setting("risk_settings", json.dumps(settings_dict))



_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
