from datetime import datetime, time, date
from typing import Optional, Union
import pytz

IST = pytz.timezone("Asia/Kolkata")

# Standard NSE Equity trading hours
MARKET_OPEN_TIME = time(9, 15, 0)
MARKET_CLOSE_TIME = time(15, 30, 0)

# 2026 NSE Equity Holidays (Indicative official list)
NSE_HOLIDAYS_2026 = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 6),   # Mahashivratri
    date(2026, 3, 20),  # Id-Ul-Fitr
    date(2026, 3, 25),  # Holi
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 5, 27),  # Bakri Id
    date(2026, 8, 15),  # Independence Day
    date(2026, 9, 4),   # Milad-un-Nabi
    date(2026, 10, 2),  # Mahatma Gandhi Jayanti
    date(2026, 10, 20), # Dussehra
    date(2026, 11, 8),  # Diwali Laxmi Pujan
    date(2026, 11, 10), # Diwali Balipratipada
    date(2026, 11, 24), # Gurunanak Jayanti
    date(2026, 12, 25), # Christmas
}


def get_ist_now() -> datetime:
    """Returns current datetime in Asia/Kolkata timezone."""
    return datetime.now(IST)


def to_ist(dt_or_timestamp: Union[datetime, int, float, str]) -> datetime:
    """Converts a datetime or epoch ms/sec timestamp to an IST timezone-aware datetime."""
    if isinstance(dt_or_timestamp, (int, float)):
        # If timestamp is in milliseconds (typical for market feeds > 1e11)
        if dt_or_timestamp > 1e11:
            seconds = dt_or_timestamp / 1000.0
        else:
            seconds = float(dt_or_timestamp)
        return datetime.fromtimestamp(seconds, tz=IST)
    elif isinstance(dt_or_timestamp, datetime):
        if dt_or_timestamp.tzinfo is None:
            return IST.localize(dt_or_timestamp)
        return dt_or_timestamp.astimezone(IST)
    elif isinstance(dt_or_timestamp, str):
        try:
            # Try parsing ISO format
            dt = datetime.fromisoformat(dt_or_timestamp)
            if dt.tzinfo is None:
                return IST.localize(dt)
            return dt.astimezone(IST)
        except Exception:
            # Try parsing timestamp string
            val = float(dt_or_timestamp)
            return to_ist(val)
    raise ValueError(f"Cannot convert {type(dt_or_timestamp)} to IST datetime")


def format_ist_datetime(dt_or_timestamp: Union[datetime, int, float, str], fmt: str = "%Y-%m-%d %H:%M:%S IST") -> str:
    """Formats a datetime or timestamp in IST."""
    return to_ist(dt_or_timestamp).strftime(fmt)


def is_nse_holiday(dt: Optional[datetime] = None) -> bool:
    """Checks whether the given date is an official NSE trading holiday or weekend."""
    if dt is None:
        dt = get_ist_now()
    else:
        dt = to_ist(dt)
    
    # Check weekend (5: Saturday, 6: Sunday)
    if dt.weekday() in (5, 6):
        return True
    
    return dt.date() in NSE_HOLIDAYS_2026


def is_market_session_open(dt: Optional[datetime] = None) -> bool:
    """
    Determines if normal NSE equity market hours are open (09:15 to 15:30 IST on working days).
    """
    if dt is None:
        dt = get_ist_now()
    else:
        dt = to_ist(dt)
    
    if is_nse_holiday(dt):
        return False
    
    current_time = dt.time()
    return MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME

