from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any


@dataclass
class CandlestickPattern:
    pattern_name: str                   # 'BULLISH_ENGULFING', 'BEARISH_ENGULFING', 'HAMMER', 'SHOOTING_STAR', 'DOJI', 'INSIDE_BAR', 'BREAKOUT_RETEST'
    candle_timestamp: int
    classification: str                 # 'BULLISH', 'BEARISH', 'NEUTRAL'
    price_levels: Dict[str, float]      # Key levels (open, high, low, close)
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "candle_timestamp": self.candle_timestamp,
            "classification": self.classification,
            "price_levels": self.price_levels,
            "explanation": self.explanation
        }


def detect_candlestick_patterns(candles: List[Dict[str, Any]]) -> List[CandlestickPattern]:
    """
    Evaluates completed candles for mathematical candlestick patterns.
    Analyzes the latest completed candle (index -1) and its relationship
    with preceding candles (index -2, -3).
    """
    if len(candles) < 2:
        return []

    c_curr = candles[-1]
    c_prev = candles[-2]

    curr_open = float(c_curr["open"])
    curr_high = float(c_curr["high"])
    curr_low = float(c_curr["low"])
    curr_close = float(c_curr["close"])
    curr_time = int(c_curr.get("open_time", 0))

    prev_open = float(c_prev["open"])
    prev_high = float(c_prev["high"])
    prev_low = float(c_prev["low"])
    prev_close = float(c_prev["close"])

    curr_body = abs(curr_close - curr_open)
    curr_range = curr_high - curr_low
    prev_body = abs(prev_close - prev_open)

    # Avoid zero division
    if curr_range <= 0.0001:
        curr_range = 0.01

    curr_is_bullish = curr_close > curr_open
    curr_is_bearish = curr_close < curr_open
    prev_is_bullish = prev_close > prev_open
    prev_is_bearish = prev_close < prev_open

    upper_wick = curr_high - max(curr_open, curr_close)
    lower_wick = min(curr_open, curr_close) - curr_low

    patterns: List[CandlestickPattern] = []

    # 1. Bullish Engulfing:
    # Prior candle bearish, current candle bullish, current body completely engulfs prior body
    if prev_is_bearish and curr_is_bullish:
        if curr_open <= prev_close and curr_close >= prev_open and curr_body > prev_body:
            patterns.append(CandlestickPattern(
                pattern_name="BULLISH_ENGULFING",
                candle_timestamp=curr_time,
                classification="BULLISH",
                price_levels={"open": curr_open, "high": curr_high, "low": curr_low, "close": curr_close},
                explanation=f"Bullish engulfing: Green candle body ({curr_body:.2f}) completely engulfed prior red body ({prev_body:.2f})."
            ))

    # 2. Bearish Engulfing:
    # Prior candle bullish, current candle bearish, current body completely engulfs prior body
    if prev_is_bullish and curr_is_bearish:
        if curr_open >= prev_close and curr_close <= prev_open and curr_body > prev_body:
            patterns.append(CandlestickPattern(
                pattern_name="BEARISH_ENGULFING",
                candle_timestamp=curr_time,
                classification="BEARISH",
                price_levels={"open": curr_open, "high": curr_high, "low": curr_low, "close": curr_close},
                explanation=f"Bearish engulfing: Red candle body ({curr_body:.2f}) completely engulfed prior green body ({prev_body:.2f})."
            ))

    # 3. Hammer:
    # Small real body at the upper end of range, long lower shadow >= 2x body, tiny/no upper shadow (<= 0.5x body)
    if lower_wick >= (curr_body * 2.0) and round(upper_wick, 2) <= round(curr_body * 0.5, 2) and curr_body > 0:
        patterns.append(CandlestickPattern(
            pattern_name="HAMMER",
            candle_timestamp=curr_time,
            classification="BULLISH",
            price_levels={"low_rejection": curr_low, "close": curr_close},
            explanation=f"Hammer: Long lower shadow ({lower_wick:.2f} >= 2x body {curr_body:.2f}) showing strong intraday buying rejection."
        ))

    # 4. Shooting Star:
    # Small real body at lower end of range, long upper shadow >= 2x body, tiny/no lower shadow (<= 0.5x body)
    if upper_wick >= (curr_body * 2.0) and round(lower_wick, 2) <= round(curr_body * 0.5, 2) and curr_body > 0:
        patterns.append(CandlestickPattern(
            pattern_name="SHOOTING_STAR",
            candle_timestamp=curr_time,
            classification="BEARISH",
            price_levels={"high_rejection": curr_high, "close": curr_close},
            explanation=f"Shooting star: Long upper shadow ({upper_wick:.2f} >= 2x body {curr_body:.2f}) showing overhead supply rejection."
        ))

    # 5. Doji:
    # Real body is negligible compared to total range (body <= 10% of total range)
    if curr_body <= (curr_range * 0.10):
        patterns.append(CandlestickPattern(
            pattern_name="DOJI",
            candle_timestamp=curr_time,
            classification="NEUTRAL",
            price_levels={"high": curr_high, "low": curr_low, "close": curr_close},
            explanation=f"Doji: Open and close virtually identical (body {curr_body:.2f} <= 10% range {curr_range:.2f}), reflecting equilibrium."
        ))

    # 6. Inside Bar:
    # High is lower than prior high, and Low is higher than prior low (range contained within prior bar)
    if curr_high <= prev_high and curr_low >= prev_low:
        patterns.append(CandlestickPattern(
            pattern_name="INSIDE_BAR",
            candle_timestamp=curr_time,
            classification="NEUTRAL",
            price_levels={"mother_high": prev_high, "mother_low": prev_low},
            explanation=f"Inside bar: Current range [{curr_low:.2f}, {curr_high:.2f}] strictly contained within previous bar [{prev_low:.2f}, {prev_high:.2f}]."
        ))

    # 7. Breakout and Retest Pattern:
    # If 3 or more candles available: candle -3 tests/closes below a level, candle -2 breaks out strongly, candle -1 pulls back and holds
    if len(candles) >= 3:
        c_two_ago = candles[-3]
        two_close = float(c_two_ago["close"])
        two_high = float(c_two_ago["high"])
        if prev_close > two_high and curr_low <= two_high * 1.002 and curr_close > two_high:
            patterns.append(CandlestickPattern(
                pattern_name="BREAKOUT_RETEST",
                candle_timestamp=curr_time,
                classification="BULLISH",
                price_levels={"breakout_level": two_high, "retest_low": curr_low},
                explanation=f"Breakout & retest: Prior high {two_high:.2f} broken by {prev_close:.2f} and successfully retested at {curr_low:.2f}."
            ))

    return patterns
