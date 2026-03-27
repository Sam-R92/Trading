"""Bot Agent - Automated Trading with Candlestick Pattern Detection & Image-Based Matching.

Uses candlestick patterns, reference image training data, and VWAP/VWMA strategies
to identify trade setups and execute orders when specific conditions are met.
"""

import threading
import time
import os
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from enum import Enum

# Optional: image-based pattern matching
try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


# ─── Candlestick Pattern Definitions ────────────────────────────────────────

class CandleStick:
    """Represents a single candlestick with OHLCV data."""

    __slots__ = ('open', 'high', 'low', 'close', 'volume', 'timestamp')

    def __init__(self, open_p: float, high: float, low: float, close: float,
                 volume: float = 0, timestamp: str = ""):
        self.open = open_p
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.timestamp = timestamp

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_percent(self) -> float:
        return (self.body / self.range * 100) if self.range > 0 else 0


class CandlestickPatternDetector:
    """Detects standard candlestick patterns from OHLCV data."""

    # Pattern categories
    BULLISH_PATTERNS = [
        'hammer', 'bullish_engulfing', 'morning_star', 'three_white_soldiers',
        'bullish_harami', 'piercing_line', 'dragonfly_doji', 'inverted_hammer'
    ]
    BEARISH_PATTERNS = [
        'hanging_man', 'bearish_engulfing', 'evening_star', 'three_black_crows',
        'bearish_harami', 'dark_cloud_cover', 'gravestone_doji', 'shooting_star'
    ]
    NEUTRAL_PATTERNS = ['doji', 'spinning_top']

    ALL_PATTERNS = BULLISH_PATTERNS + BEARISH_PATTERNS + NEUTRAL_PATTERNS

    @staticmethod
    def detect_all(candles: List[CandleStick]) -> List[Dict]:
        """Detect all candlestick patterns in the candle series.

        Returns list of detected patterns with signal info.
        """
        if len(candles) < 3:
            return []

        detected = []
        detector = CandlestickPatternDetector

        # Single-candle patterns (check last candle)
        c = candles[-1]
        prev = candles[-2] if len(candles) >= 2 else None
        prev2 = candles[-3] if len(candles) >= 3 else None

        # --- Doji ---
        if c.range > 0 and c.body_percent < 5:
            detected.append({
                'pattern': 'doji',
                'signal': 'NEUTRAL',
                'strength': 50,
                'description': 'Doji - Indecision, possible reversal',
                'candle_index': -1
            })

        # --- Spinning Top ---
        if c.range > 0 and 5 <= c.body_percent <= 30 and c.upper_shadow > c.body and c.lower_shadow > c.body:
            detected.append({
                'pattern': 'spinning_top',
                'signal': 'NEUTRAL',
                'strength': 40,
                'description': 'Spinning Top - Indecision',
                'candle_index': -1
            })

        # --- Hammer (bullish reversal at bottom) ---
        if (c.range > 0 and c.lower_shadow >= 2 * c.body and c.upper_shadow < c.body * 0.3
                and prev and prev.is_bearish):
            detected.append({
                'pattern': 'hammer',
                'signal': 'BUY',
                'strength': 75,
                'description': 'Hammer - Bullish reversal signal',
                'candle_index': -1
            })

        # --- Inverted Hammer ---
        if (c.range > 0 and c.upper_shadow >= 2 * c.body and c.lower_shadow < c.body * 0.3
                and prev and prev.is_bearish):
            detected.append({
                'pattern': 'inverted_hammer',
                'signal': 'BUY',
                'strength': 65,
                'description': 'Inverted Hammer - Possible bullish reversal',
                'candle_index': -1
            })

        # --- Hanging Man (bearish reversal at top) ---
        if (c.range > 0 and c.lower_shadow >= 2 * c.body and c.upper_shadow < c.body * 0.3
                and prev and prev.is_bullish):
            detected.append({
                'pattern': 'hanging_man',
                'signal': 'SELL',
                'strength': 70,
                'description': 'Hanging Man - Bearish reversal signal',
                'candle_index': -1
            })

        # --- Shooting Star ---
        if (c.range > 0 and c.upper_shadow >= 2 * c.body and c.lower_shadow < c.body * 0.3
                and prev and prev.is_bullish):
            detected.append({
                'pattern': 'shooting_star',
                'signal': 'SELL',
                'strength': 70,
                'description': 'Shooting Star - Bearish reversal signal',
                'candle_index': -1
            })

        # --- Dragonfly Doji (bullish) ---
        if (c.range > 0 and c.body_percent < 5 and c.lower_shadow > c.range * 0.6
                and c.upper_shadow < c.range * 0.1):
            detected.append({
                'pattern': 'dragonfly_doji',
                'signal': 'BUY',
                'strength': 70,
                'description': 'Dragonfly Doji - Strong bullish reversal',
                'candle_index': -1
            })

        # --- Gravestone Doji (bearish) ---
        if (c.range > 0 and c.body_percent < 5 and c.upper_shadow > c.range * 0.6
                and c.lower_shadow < c.range * 0.1):
            detected.append({
                'pattern': 'gravestone_doji',
                'signal': 'SELL',
                'strength': 70,
                'description': 'Gravestone Doji - Strong bearish reversal',
                'candle_index': -1
            })

        # Two-candle patterns
        if prev:
            # --- Bullish Engulfing ---
            if (prev.is_bearish and c.is_bullish
                    and c.open <= prev.close and c.close >= prev.open
                    and c.body > prev.body):
                detected.append({
                    'pattern': 'bullish_engulfing',
                    'signal': 'BUY',
                    'strength': 80,
                    'description': 'Bullish Engulfing - Strong buy signal',
                    'candle_index': -1
                })

            # --- Bearish Engulfing ---
            if (prev.is_bullish and c.is_bearish
                    and c.open >= prev.close and c.close <= prev.open
                    and c.body > prev.body):
                detected.append({
                    'pattern': 'bearish_engulfing',
                    'signal': 'SELL',
                    'strength': 80,
                    'description': 'Bearish Engulfing - Strong sell signal',
                    'candle_index': -1
                })

            # --- Bullish Harami ---
            if (prev.is_bearish and c.is_bullish
                    and c.open > prev.close and c.close < prev.open
                    and c.body < prev.body * 0.5):
                detected.append({
                    'pattern': 'bullish_harami',
                    'signal': 'BUY',
                    'strength': 60,
                    'description': 'Bullish Harami - Potential reversal',
                    'candle_index': -1
                })

            # --- Bearish Harami ---
            if (prev.is_bullish and c.is_bearish
                    and c.open < prev.close and c.close > prev.open
                    and c.body < prev.body * 0.5):
                detected.append({
                    'pattern': 'bearish_harami',
                    'signal': 'SELL',
                    'strength': 60,
                    'description': 'Bearish Harami - Potential reversal',
                    'candle_index': -1
                })

            # --- Piercing Line (bullish) ---
            if (prev.is_bearish and c.is_bullish
                    and c.open < prev.low
                    and c.close > (prev.open + prev.close) / 2):
                detected.append({
                    'pattern': 'piercing_line',
                    'signal': 'BUY',
                    'strength': 70,
                    'description': 'Piercing Line - Bullish reversal',
                    'candle_index': -1
                })

            # --- Dark Cloud Cover (bearish) ---
            if (prev.is_bullish and c.is_bearish
                    and c.open > prev.high
                    and c.close < (prev.open + prev.close) / 2):
                detected.append({
                    'pattern': 'dark_cloud_cover',
                    'signal': 'SELL',
                    'strength': 70,
                    'description': 'Dark Cloud Cover - Bearish reversal',
                    'candle_index': -1
                })

        # Three-candle patterns
        if prev and prev2:
            # --- Morning Star (bullish) ---
            if (prev2.is_bearish and prev2.body_percent > 50
                    and prev.body_percent < 20
                    and c.is_bullish and c.body_percent > 50
                    and c.close > (prev2.open + prev2.close) / 2):
                detected.append({
                    'pattern': 'morning_star',
                    'signal': 'BUY',
                    'strength': 85,
                    'description': 'Morning Star - Very strong bullish reversal',
                    'candle_index': -1
                })

            # --- Evening Star (bearish) ---
            if (prev2.is_bullish and prev2.body_percent > 50
                    and prev.body_percent < 20
                    and c.is_bearish and c.body_percent > 50
                    and c.close < (prev2.open + prev2.close) / 2):
                detected.append({
                    'pattern': 'evening_star',
                    'signal': 'SELL',
                    'strength': 85,
                    'description': 'Evening Star - Very strong bearish reversal',
                    'candle_index': -1
                })

            # --- Three White Soldiers (bullish) ---
            if (prev2.is_bullish and prev.is_bullish and c.is_bullish
                    and prev.close > prev2.close and c.close > prev.close
                    and prev2.body_percent > 40 and prev.body_percent > 40
                    and c.body_percent > 40):
                detected.append({
                    'pattern': 'three_white_soldiers',
                    'signal': 'BUY',
                    'strength': 90,
                    'description': 'Three White Soldiers - Very strong bullish continuation',
                    'candle_index': -1
                })

            # --- Three Black Crows (bearish) ---
            if (prev2.is_bearish and prev.is_bearish and c.is_bearish
                    and prev.close < prev2.close and c.close < prev.close
                    and prev2.body_percent > 40 and prev.body_percent > 40
                    and c.body_percent > 40):
                detected.append({
                    'pattern': 'three_black_crows',
                    'signal': 'SELL',
                    'strength': 90,
                    'description': 'Three Black Crows - Very strong bearish continuation',
                    'candle_index': -1
                })

        return detected


# ─── Image-Based Pattern Matching ────────────────────────────────────────────

class ChartPatternMatcher:
    """Matches current price action against reference chart pattern images.

    Uses normalized OHLC sequences to compare against reference patterns stored
    as images or data files. When PIL is available, can load reference chart
    screenshots; otherwise works with stored numeric pattern templates.
    """

    def __init__(self, reference_dir: str = ""):
        if not reference_dir:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            reference_dir = os.path.join(app_dir, "data", "bot_patterns")

        self.reference_dir = reference_dir
        os.makedirs(self.reference_dir, exist_ok=True)

        # Built-in chart pattern templates (normalized price sequences)
        self.builtin_patterns = self._load_builtin_patterns()

        # User-supplied reference patterns
        self.user_patterns: List[Dict] = []
        self._load_user_patterns()

    def _load_builtin_patterns(self) -> Dict[str, Dict]:
        """Built-in normalized chart pattern templates."""
        return {
            'double_bottom': {
                'signal': 'BUY',
                'strength': 80,
                'description': 'Double Bottom - Bullish reversal',
                # Normalized price sequence (0-1 range): down, bottom, up, bottom, breakout
                'sequence': [1.0, 0.7, 0.3, 0.1, 0.3, 0.5, 0.3, 0.1, 0.3, 0.6, 0.8, 1.0],
                'tolerance': 0.15
            },
            'double_top': {
                'signal': 'SELL',
                'strength': 80,
                'description': 'Double Top - Bearish reversal',
                'sequence': [0.0, 0.3, 0.7, 0.9, 0.7, 0.5, 0.7, 0.9, 0.7, 0.4, 0.2, 0.0],
                'tolerance': 0.15
            },
            'head_and_shoulders': {
                'signal': 'SELL',
                'strength': 85,
                'description': 'Head & Shoulders - Strong bearish reversal',
                'sequence': [0.2, 0.5, 0.7, 0.5, 0.3, 0.6, 0.9, 1.0, 0.6, 0.3, 0.5, 0.7, 0.5, 0.2, 0.0],
                'tolerance': 0.15
            },
            'inv_head_and_shoulders': {
                'signal': 'BUY',
                'strength': 85,
                'description': 'Inverse Head & Shoulders - Strong bullish reversal',
                'sequence': [0.8, 0.5, 0.3, 0.5, 0.7, 0.4, 0.1, 0.0, 0.4, 0.7, 0.5, 0.3, 0.5, 0.8, 1.0],
                'tolerance': 0.15
            },
            'ascending_triangle': {
                'signal': 'BUY',
                'strength': 70,
                'description': 'Ascending Triangle - Bullish breakout',
                'sequence': [0.1, 0.5, 0.8, 0.4, 0.8, 0.5, 0.8, 0.6, 0.8, 0.7, 0.9, 1.0],
                'tolerance': 0.15
            },
            'descending_triangle': {
                'signal': 'SELL',
                'strength': 70,
                'description': 'Descending Triangle - Bearish breakdown',
                'sequence': [0.9, 0.5, 0.2, 0.6, 0.2, 0.5, 0.2, 0.4, 0.2, 0.3, 0.1, 0.0],
                'tolerance': 0.15
            },
            'cup_and_handle': {
                'signal': 'BUY',
                'strength': 80,
                'description': 'Cup & Handle - Bullish continuation',
                'sequence': [0.8, 0.6, 0.4, 0.2, 0.1, 0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 0.75, 0.7, 0.75, 0.9, 1.0],
                'tolerance': 0.15
            },
            'v_reversal_bullish': {
                'signal': 'BUY',
                'strength': 75,
                'description': 'V-Bottom Reversal - Sharp bullish recovery',
                'sequence': [1.0, 0.8, 0.5, 0.2, 0.0, 0.2, 0.5, 0.8, 1.0],
                'tolerance': 0.12
            },
            'v_reversal_bearish': {
                'signal': 'SELL',
                'strength': 75,
                'description': 'Inverted V Reversal - Sharp bearish drop',
                'sequence': [0.0, 0.2, 0.5, 0.8, 1.0, 0.8, 0.5, 0.2, 0.0],
                'tolerance': 0.12
            }
        }

    def _load_user_patterns(self):
        """Load user-defined reference patterns from disk."""
        patterns_file = os.path.join(self.reference_dir, "user_patterns.json")
        if os.path.exists(patterns_file):
            try:
                with open(patterns_file, 'r') as f:
                    self.user_patterns = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.user_patterns = []

    def save_user_pattern(self, name: str, signal: str, description: str,
                          price_sequence: List[float], image_path: str = ""):
        """Save a user-defined pattern from reference data.

        Args:
            name: Pattern name
            signal: 'BUY' or 'SELL'
            description: Pattern description
            price_sequence: Normalized (0-1) price sequence
            image_path: Optional path to reference chart image
        """
        pattern = {
            'name': name,
            'signal': signal,
            'strength': 70,
            'description': description,
            'sequence': price_sequence,
            'tolerance': 0.15,
            'image_path': image_path,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        self.user_patterns.append(pattern)

        patterns_file = os.path.join(self.reference_dir, "user_patterns.json")
        with open(patterns_file, 'w') as f:
            json.dump(self.user_patterns, f, indent=2)

        return pattern

    def extract_pattern_from_image(self, image_path: str) -> Optional[List[float]]:
        """Extract a normalized price sequence from a chart screenshot.

        Analyzes the image to trace the price line/candles and produces a
        normalized 0-1 sequence representing the pattern shape.
        """
        if not HAS_PIL:
            return None

        try:
            img = Image.open(image_path).convert('L')  # Grayscale
            img = img.resize((200, 150))  # Normalize size
            pixels = np.array(img)

            # Find the darkest (price line) pixels in each column
            sequence = []
            width = pixels.shape[1]
            sample_points = min(20, width)
            step = width // sample_points

            for i in range(0, width, step):
                col = pixels[:, i]
                # The price line is typically darker - find the darkest region
                min_idx = np.argmin(col)
                # Normalize: 0 = top of image (high price), 1 = bottom (low)
                # Invert because in charts, top = high price
                normalized = 1.0 - (min_idx / pixels.shape[0])
                sequence.append(round(normalized, 3))

            # Normalize the sequence to 0-1 range
            if sequence:
                min_val = min(sequence)
                max_val = max(sequence)
                val_range = max_val - min_val
                if val_range > 0:
                    sequence = [round((v - min_val) / val_range, 3) for v in sequence]

            return sequence

        except Exception as e:
            print(f"⚠️ Image pattern extraction failed: {e}")
            return None

    def match_pattern(self, price_data: List[float]) -> List[Dict]:
        """Match current price data against all known patterns.

        Args:
            price_data: Recent close prices (raw, not normalized)

        Returns:
            List of matching patterns with confidence scores
        """
        if len(price_data) < 5:
            return []

        # Normalize input data to 0-1 range
        min_p = min(price_data)
        max_p = max(price_data)
        price_range = max_p - min_p
        if price_range == 0:
            return []

        normalized = [(p - min_p) / price_range for p in price_data]

        matches = []

        # Check built-in patterns
        for name, pattern in self.builtin_patterns.items():
            similarity = self._compute_similarity(normalized, pattern['sequence'])
            if similarity >= (1.0 - pattern['tolerance']):
                confidence = int(similarity * 100)
                matches.append({
                    'pattern': name,
                    'signal': pattern['signal'],
                    'strength': min(pattern['strength'], confidence),
                    'confidence': confidence,
                    'description': pattern['description'],
                    'source': 'builtin'
                })

        # Check user patterns
        for pattern in self.user_patterns:
            seq = pattern.get('sequence', [])
            if seq:
                similarity = self._compute_similarity(normalized, seq)
                tolerance = pattern.get('tolerance', 0.15)
                if similarity >= (1.0 - tolerance):
                    confidence = int(similarity * 100)
                    matches.append({
                        'pattern': pattern['name'],
                        'signal': pattern['signal'],
                        'strength': min(pattern.get('strength', 70), confidence),
                        'confidence': confidence,
                        'description': pattern.get('description', ''),
                        'source': 'user'
                    })

        # Sort by confidence descending
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches

    @staticmethod
    def _compute_similarity(seq_a: List[float], seq_b: List[float]) -> float:
        """Compute similarity between two normalized sequences using DTW-inspired approach.

        Resamples both sequences to equal length, then computes correlation.
        """
        # Resample to same length
        target_len = min(len(seq_a), len(seq_b))
        if target_len < 3:
            return 0.0

        a = CandlestickPatternDetector._resample(seq_a, target_len)
        b = CandlestickPatternDetector._resample(seq_b, target_len)

        # Compute mean absolute error based similarity
        total_error = sum(abs(a[i] - b[i]) for i in range(target_len))
        mae = total_error / target_len

        # Convert MAE to similarity score (0-1)
        return max(0.0, 1.0 - mae)

    @staticmethod
    def _resample(seq: List[float], target_len: int) -> List[float]:
        """Resample a sequence to target length using linear interpolation."""
        if len(seq) == target_len:
            return list(seq)

        result = []
        for i in range(target_len):
            pos = i * (len(seq) - 1) / (target_len - 1) if target_len > 1 else 0
            lower = int(pos)
            upper = min(lower + 1, len(seq) - 1)
            frac = pos - lower
            val = seq[lower] * (1 - frac) + seq[upper] * frac
            result.append(val)
        return result


# Attach resample utility to detector for cross-use
CandlestickPatternDetector._resample = ChartPatternMatcher._resample


# ─── VWAP / VWMA Calculations ───────────────────────────────────────────────

class VWAPCalculator:
    """Compute intraday VWAP and rolling VWMA from candle data."""

    @staticmethod
    def compute_vwap(candles: List[CandleStick]) -> List[float]:
        """Cumulative intraday VWAP for each candle.

        VWAP = cumulative(typical_price * volume) / cumulative(volume)
        typical_price = (high + low + close) / 3
        """
        vwap = []
        cum_tp_vol = 0.0
        cum_vol = 0.0
        for c in candles:
            tp = (c.high + c.low + c.close) / 3.0
            cum_tp_vol += tp * c.volume
            cum_vol += c.volume
            vwap.append(cum_tp_vol / cum_vol if cum_vol > 0 else tp)
        return vwap

    @staticmethod
    def compute_vwma(candles: List[CandleStick], period: int) -> List[Optional[float]]:
        """Rolling Volume-Weighted Moving Average.

        VWMA(n) = sum(close_i * volume_i, n) / sum(volume_i, n)
        Returns None for indices where not enough data.
        """
        result: List[Optional[float]] = []
        for i in range(len(candles)):
            if i < period - 1:
                result.append(None)
                continue
            window = candles[i - period + 1: i + 1]
            total_cv = sum(c.close * c.volume for c in window)
            total_v = sum(c.volume for c in window)
            result.append(total_cv / total_v if total_v > 0 else candles[i].close)
        return result

    @staticmethod
    def day_low(candles: List[CandleStick]) -> float:
        """Return the lowest low across all candles (intraday low)."""
        if not candles:
            return 0.0
        return min(c.low for c in candles)

    @staticmethod
    def day_high(candles: List[CandleStick]) -> float:
        """Return the highest high across all candles (intraday high)."""
        if not candles:
            return 0.0
        return max(c.high for c in candles)


# ─── VWAP Strategy State Machines ────────────────────────────────────────────

class VWAPRejectionState(Enum):
    """States for Strategy 1 – VWAP Rejection Short."""
    WAITING_OPEN_BELOW = "waiting_open_below"      # Price must open below VWAP & VWMA
    WAITING_CROSS_ABOVE = "waiting_cross_above"     # Wait for price to cross above VWAP
    WAITING_CROSS_BELOW = "waiting_cross_below"     # Wait for price to fall back below VWAP
    WAITING_REJECTION = "waiting_rejection_candle"  # Wait for non-touch rejection candle
    SIGNAL_READY = "signal_ready"                   # Entry triggered


class PullbackFailureState(Enum):
    """States for Strategy 2 – Pullback Failure Short."""
    WAITING_BELOW_VWAP = "waiting_below_vwap"       # Price must be below VWAP
    WAITING_BOTTOM = "waiting_bottom"                # Detect local minimum
    WAITING_PULLBACK = "waiting_pullback"            # Price pulling back up → alert
    CHECKING_FAILURE = "checking_vwma_failure"       # Check failure at VWMA levels
    SIGNAL_READY = "signal_ready"                    # Entry triggered


class VWAPStrategyEngine:
    """Runs both VWAP-based strategies against live candle data.

    Strategy 1 – VWAP Rejection Short
    ==================================
    Condition : Price opens below VWAP and VWMA.
    Sequence  : Price crosses UP above VWAP → comes back DOWN below VWAP →
                a "rejection candle" forms whose HIGH stays below VWAP
                (non-touchable candle) → ENTER PE on that candle close.

    Strategy 2 – Pullback Failure Short
    ====================================
    Condition : Price is below VWAP.
    Sequence  : Price hits a local bottom → pulls back upward (alert) →
                check if price fails at VWMA levels:
                  • 1-min VWMA failure  → enter immediately
                  • 3-min VWMA failure  → enter
                  • middle (1–3 min VWMA) failure → enter
                  • no failure candle   → skip
                Target: below day low.
    """

    def __init__(self, on_log=None, on_alert=None):
        # Strategy 1 state
        self.s1_state = VWAPRejectionState.WAITING_OPEN_BELOW
        self.s1_enabled = True
        self.s1_cross_above_price = 0.0   # price when it crossed above VWAP

        # Strategy 2 state
        self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
        self.s2_enabled = True
        self.s2_bottom_price = 0.0
        self.s2_bottom_idx = -1
        self.s2_pullback_high = 0.0
        self.s2_alert_sent = False
        self.s2_failure_wait_count = 0    # candles waited for failure

        # Configuration
        self.vwma_1m_period = 1     # 1-candle VWMA (same as 1-min if 1-min candles)
        self.vwma_3m_period = 3     # 3-candle VWMA
        self.max_failure_wait = 5   # max candles to wait for failure before skipping

        # Callbacks
        self.on_log = on_log
        self.on_alert = on_alert    # fn(alert_dict) - for alert notifications

    def _log(self, msg: str, level: str = 'info'):
        if self.on_log:
            try:
                self.on_log(msg, level)
            except Exception:
                pass

    def reset(self):
        """Reset both strategies to initial state (e.g. new trading day)."""
        self.s1_state = VWAPRejectionState.WAITING_OPEN_BELOW
        self.s1_cross_above_price = 0.0
        self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
        self.s2_bottom_price = 0.0
        self.s2_bottom_idx = -1
        self.s2_pullback_high = 0.0
        self.s2_alert_sent = False
        self.s2_failure_wait_count = 0

    def evaluate(self, candles: List[CandleStick]) -> List[Dict]:
        """Run both strategies on the candle series.

        Returns a list of signal dicts (may be empty, one, or two).
        Each signal contains: strategy, signal, strength, description, entry_price, target.
        """
        if len(candles) < 5:
            return []

        signals = []

        # Compute indicators
        vwap = VWAPCalculator.compute_vwap(candles)
        vwma_1 = VWAPCalculator.compute_vwma(candles, self.vwma_1m_period)
        vwma_3 = VWAPCalculator.compute_vwma(candles, self.vwma_3m_period)
        d_low = VWAPCalculator.day_low(candles)

        last = candles[-1]
        prev = candles[-2]
        cur_vwap = vwap[-1]
        prev_vwap = vwap[-2]
        cur_vwma1 = vwma_1[-1]
        cur_vwma3 = vwma_3[-1] if vwma_3[-1] is not None else cur_vwap

        # ── Strategy 1: VWAP Rejection Short ─────────────────────────────
        if self.s1_enabled:
            s1 = self._eval_vwap_rejection(
                candles, last, prev, cur_vwap, prev_vwap, vwap, d_low
            )
            if s1:
                signals.append(s1)

        # ── Strategy 2: Pullback Failure Short ───────────────────────────
        if self.s2_enabled:
            s2 = self._eval_pullback_failure(
                candles, last, prev, cur_vwap, prev_vwap,
                cur_vwma1, cur_vwma3, vwma_1, vwma_3, d_low
            )
            if s2:
                signals.append(s2)

        return signals

    # ── Strategy 1 implementation ────────────────────────────────────────

    def _eval_vwap_rejection(self, candles, last, prev, cur_vwap, prev_vwap,
                              vwap_series, day_low_val) -> Optional[Dict]:

        open_candle = candles[0]
        open_vwap = vwap_series[0] if vwap_series else cur_vwap

        if self.s1_state == VWAPRejectionState.WAITING_OPEN_BELOW:
            # Check: price opened below VWAP
            if open_candle.open < open_vwap:
                self.s1_state = VWAPRejectionState.WAITING_CROSS_ABOVE
                self._log("📌 S1: Price opened below VWAP – watching for cross above", 'info')
            else:
                # Price opened above VWAP → Strategy 1 not applicable today
                return None

        if self.s1_state == VWAPRejectionState.WAITING_CROSS_ABOVE:
            # Did price cross above VWAP?
            if last.close > cur_vwap or last.high > cur_vwap:
                self.s1_state = VWAPRejectionState.WAITING_CROSS_BELOW
                self.s1_cross_above_price = last.close
                self._log(
                    f"📈 S1: Price crossed ABOVE VWAP ({cur_vwap:.2f}) – "
                    f"waiting for drop back below", 'signal'
                )
            return None

        if self.s1_state == VWAPRejectionState.WAITING_CROSS_BELOW:
            # Did price fall back below VWAP?
            if last.close < cur_vwap:
                self.s1_state = VWAPRejectionState.WAITING_REJECTION
                self._log(
                    f"📉 S1: Price dropped back BELOW VWAP ({cur_vwap:.2f}) – "
                    f"waiting for rejection candle", 'signal'
                )
            return None

        if self.s1_state == VWAPRejectionState.WAITING_REJECTION:
            # Rejection candle: closes below VWAP AND high does NOT touch VWAP
            # (non-touchable candle)
            if last.close < cur_vwap and last.high < cur_vwap:
                self.s1_state = VWAPRejectionState.SIGNAL_READY
                self._log(
                    f"🔴 S1: REJECTION CANDLE confirmed! "
                    f"High={last.high:.2f} < VWAP={cur_vwap:.2f} | "
                    f"Close={last.close:.2f} → ENTER PE on candle close",
                    'signal'
                )
                signal = {
                    'pattern': 'vwap_rejection_short',
                    'signal': 'SELL',
                    'strength': 85,
                    'type': 'vwap_strategy',
                    'description': (
                        f"VWAP Rejection Short – Price opened below VWAP, crossed above, "
                        f"fell back & rejection candle formed (H={last.high:.2f} < VWAP={cur_vwap:.2f})"
                    ),
                    'entry_price': last.close,
                    'target': day_low_val,
                    'vwap': cur_vwap,
                    'strategy': 'S1_VWAP_REJECTION'
                }
                # Reset for next setup
                self.s1_state = VWAPRejectionState.WAITING_OPEN_BELOW
                return signal

            # If candle's high touches/exceeds VWAP, reset to waiting for another cross below
            if last.high >= cur_vwap:
                # Price touched VWAP again — not a clean rejection
                if last.close > cur_vwap:
                    # Went back above — reset to WAITING_CROSS_BELOW
                    self.s1_state = VWAPRejectionState.WAITING_CROSS_BELOW
                    self._log("↩️ S1: Candle touched VWAP again – resetting to wait for cross below", 'info')
            return None

        if self.s1_state == VWAPRejectionState.SIGNAL_READY:
            self.s1_state = VWAPRejectionState.WAITING_OPEN_BELOW
            return None

        return None

    # ── Strategy 2 implementation ────────────────────────────────────────

    def _eval_pullback_failure(self, candles, last, prev, cur_vwap, prev_vwap,
                                cur_vwma1, cur_vwma3, vwma1_series, vwma3_series,
                                day_low_val) -> Optional[Dict]:

        if self.s2_state == PullbackFailureState.WAITING_BELOW_VWAP:
            if last.close < cur_vwap:
                self.s2_state = PullbackFailureState.WAITING_BOTTOM
                self.s2_bottom_price = last.low
                self.s2_bottom_idx = len(candles) - 1
                self._log(
                    f"📌 S2: Price below VWAP ({cur_vwap:.2f}) – tracking for bottom",
                    'info'
                )
            return None

        if self.s2_state == PullbackFailureState.WAITING_BOTTOM:
            # Track running low
            if last.low < self.s2_bottom_price:
                self.s2_bottom_price = last.low
                self.s2_bottom_idx = len(candles) - 1

            # Detect pullback start: price starts moving up from the bottom
            # Current candle closes higher than previous candle's close
            # AND previous was near the bottom
            if (last.close > prev.close and prev.low <= self.s2_bottom_price * 1.002):
                self.s2_state = PullbackFailureState.WAITING_PULLBACK
                self.s2_pullback_high = last.high
                self.s2_alert_sent = False
                self._log(
                    f"📈 S2: Bottom detected at {self.s2_bottom_price:.2f} – "
                    f"pullback starting, monitoring...",
                    'signal'
                )
            return None

        if self.s2_state == PullbackFailureState.WAITING_PULLBACK:
            # Track pullback high
            if last.high > self.s2_pullback_high:
                self.s2_pullback_high = last.high

            # Alert once when pullback is clearly happening
            if not self.s2_alert_sent:
                pullback_pct = 0
                if self.s2_bottom_price > 0:
                    pullback_pct = ((last.close - self.s2_bottom_price)
                                     / self.s2_bottom_price * 100)
                if pullback_pct > 0.05:  # at least 0.05% move up
                    self.s2_alert_sent = True
                    alert = {
                        'type': 'pullback_detected',
                        'message': (
                            f"⚠️ S2 ALERT: Pullback from bottom {self.s2_bottom_price:.2f} "
                            f"→ current {last.close:.2f} (+{pullback_pct:.2f}%). "
                            f"Watching for VWMA failure to enter PE."
                        ),
                        'bottom': self.s2_bottom_price,
                        'current': last.close,
                        'pullback_pct': pullback_pct
                    }
                    self._log(alert['message'], 'signal')
                    if self.on_alert:
                        try:
                            self.on_alert(alert)
                        except Exception:
                            pass

            # Transition to failure checking — price should be near VWMA levels
            # Check if price has reached VWMA zone
            if cur_vwma1 is not None and last.close >= cur_vwma1 * 0.998:
                self.s2_state = PullbackFailureState.CHECKING_FAILURE
                self.s2_failure_wait_count = 0
                self._log(
                    f"🔍 S2: Price reached VWMA zone ({cur_vwma1:.2f}) – "
                    f"checking for failure candle",
                    'signal'
                )

            # If price goes back above VWAP, abort this setup
            if last.close > cur_vwap:
                self._log("❌ S2: Price went above VWAP – aborting pullback setup", 'info')
                self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
                self.s2_alert_sent = False

            return None

        if self.s2_state == PullbackFailureState.CHECKING_FAILURE:
            self.s2_failure_wait_count += 1

            # Calculate mid-VWMA level (between 1-min and 3-min VWMA)
            mid_vwma = (cur_vwma1 + cur_vwma3) / 2 if cur_vwma1 and cur_vwma3 else cur_vwap

            failure_detected = False
            failure_type = ""

            # Check 1: 1-min VWMA failure — price falls back below 1-min VWMA
            if cur_vwma1 is not None and prev.close >= cur_vwma1 and last.close < cur_vwma1:
                failure_detected = True
                failure_type = "1-min VWMA failure"

            # Check 2: 3-min VWMA candle failure — price fails at 3-min VWMA level
            elif (cur_vwma3 is not None
                  and last.high >= cur_vwma3 * 0.998
                  and last.close < cur_vwma3
                  and last.is_bearish):
                failure_detected = True
                failure_type = "3-min VWMA candle failure"

            # Check 3: Middle failure — price fails between 1 and 3 min VWMA
            elif (cur_vwma1 is not None and cur_vwma3 is not None
                  and last.high >= mid_vwma * 0.998
                  and last.close < mid_vwma
                  and last.is_bearish):
                failure_detected = True
                failure_type = "mid VWMA (1-3 min) failure"

            if failure_detected:
                self.s2_state = PullbackFailureState.SIGNAL_READY
                self._log(
                    f"🔴 S2: {failure_type} confirmed! "
                    f"Close={last.close:.2f}, VWMA1={cur_vwma1}, VWMA3={cur_vwma3} "
                    f"→ ENTER PE, Target: below day low ({day_low_val:.2f})",
                    'signal'
                )
                signal = {
                    'pattern': 'pullback_failure_short',
                    'signal': 'SELL',
                    'strength': 80,
                    'type': 'vwap_strategy',
                    'description': (
                        f"Pullback Failure Short – Bottom at {self.s2_bottom_price:.2f}, "
                        f"{failure_type} at {last.close:.2f}. "
                        f"Target: below day low {day_low_val:.2f}"
                    ),
                    'entry_price': last.close,
                    'target': day_low_val,
                    'vwap': cur_vwap,
                    'vwma_1': cur_vwma1,
                    'vwma_3': cur_vwma3,
                    'failure_type': failure_type,
                    'strategy': 'S2_PULLBACK_FAILURE'
                }
                # Reset for next setup
                self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
                self.s2_alert_sent = False
                return signal

            # If too many candles without failure → skip (no entry)
            if self.s2_failure_wait_count >= self.max_failure_wait:
                self._log(
                    f"⏭️ S2: No failure candle after {self.max_failure_wait} candles – skipping",
                    'info'
                )
                self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
                self.s2_alert_sent = False

            # If price goes above VWAP, abort
            if last.close > cur_vwap:
                self._log("❌ S2: Price above VWAP during failure check – aborting", 'info')
                self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
                self.s2_alert_sent = False

            return None

        if self.s2_state == PullbackFailureState.SIGNAL_READY:
            self.s2_state = PullbackFailureState.WAITING_BELOW_VWAP
            self.s2_alert_sent = False
            return None

        return None

    def get_state_summary(self) -> Dict:
        """Return a human-readable summary of both strategy states."""
        return {
            's1_state': self.s1_state.value,
            's1_enabled': self.s1_enabled,
            's2_state': self.s2_state.value,
            's2_enabled': self.s2_enabled,
            's2_bottom': self.s2_bottom_price,
            's2_pullback_high': self.s2_pullback_high,
            's2_failure_wait': self.s2_failure_wait_count,
        }


# ─── Trading Bot Agent ───────────────────────────────────────────────────────

class TradingBot:
    """Automated trading bot that monitors candlestick patterns and chart patterns
    to execute orders when conditions are met.

    Works with the existing Traderchamp engine and GUI.
    """

    def __init__(self, trader=None, gui=None):
        self.trader = trader
        self.gui = gui

        # Bot state
        self.is_running = False
        self.is_paused = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Configuration
        self.config = {
            'enabled': False,
            'symbol': 'NIFTY',
            'scan_interval': 60,  # seconds between scans
            'min_confidence': 70,  # minimum confidence to trigger
            'max_trades_per_day': 5,
            'auto_execute': False,  # If False, just alerts. If True, places orders.
            'lots': 1,
            'auto_sl_percent': 5.0,
            'product_type': 'INTRADAY',
            'order_type': 'MARKET',

            # Pattern filters
            'candlestick_patterns_enabled': True,
            'chart_patterns_enabled': True,
            'enabled_candlestick_patterns': list(CandlestickPatternDetector.ALL_PATTERNS),
            'enabled_chart_patterns': list(ChartPatternMatcher({})._load_builtin_patterns().keys())
            if not callable(getattr(ChartPatternMatcher, '_load_builtin_patterns', None))
            else [],

            # Additional conditions
            'rsi_filter_enabled': True,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'volume_filter_enabled': False,
            'trend_filter_enabled': True,  # Align with MA direction

            # Market hours only
            'market_hours_only': True,

            # VWAP Strategy settings
            'vwap_rejection_enabled': True,
            'pullback_failure_enabled': True,
            'vwap_auto_execute': False,
            'vwap_scan_interval': 30,   # faster scan for intraday VWAP (seconds)
        }

        # Initialize built-in pattern list properly
        temp_matcher = ChartPatternMatcher()
        self.config['enabled_chart_patterns'] = list(temp_matcher.builtin_patterns.keys())

        # Detectors
        self.candle_detector = CandlestickPatternDetector()
        self.chart_matcher = ChartPatternMatcher()

        # VWAP Strategy Engine
        self.vwap_engine = VWAPStrategyEngine()

        # State tracking
        self.trades_today = 0
        self.last_trade_time = None
        self.trade_cooldown = 120  # seconds between trades
        self.activity_log: List[Dict] = []
        self.detected_patterns: List[Dict] = []
        self.last_scan_time = None

        # Callbacks
        self.on_signal = None  # Callback when signal detected: fn(signal_info)
        self.on_log = None     # Callback for log messages: fn(message, level)
        self.on_trade = None   # Callback when trade executed: fn(trade_info)
        self.on_vwap_alert = None  # Callback for VWAP strategy alerts: fn(alert_dict)

        # Config persistence
        self._config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config", "bot_config.json"
        )
        self._load_config()

    def _log(self, message: str, level: str = 'info'):
        """Log bot activity."""
        entry = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'message': message,
            'level': level
        }
        self.activity_log.append(entry)

        # Keep only last 500 entries
        if len(self.activity_log) > 500:
            self.activity_log = self.activity_log[-500:]

        if self.on_log:
            try:
                self.on_log(message, level)
            except Exception:
                pass

    def _load_config(self):
        """Load bot configuration from disk."""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r') as f:
                    saved = json.load(f)
                    # Merge with defaults (so new keys are included)
                    for key, value in saved.items():
                        if key in self.config:
                            self.config[key] = value
        except (json.JSONDecodeError, IOError):
            pass

    def save_config(self):
        """Save bot configuration to disk."""
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            self._log(f"Failed to save config: {e}", 'error')

    def start(self):
        """Start the bot monitoring loop."""
        if self.is_running:
            self._log("Bot is already running", 'warning')
            return

        self.is_running = True
        self.is_paused = False
        self._stop_event.clear()
        self.trades_today = 0

        # Reset VWAP strategies for new session
        self.vwap_engine.reset()
        self.vwap_engine.s1_enabled = self.config.get('vwap_rejection_enabled', True)
        self.vwap_engine.s2_enabled = self.config.get('pullback_failure_enabled', True)
        self.vwap_engine.on_log = self._log
        self.vwap_engine.on_alert = self._handle_vwap_alert

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        self._log("🤖 Bot Agent STARTED - Monitoring market patterns", 'info')

    def stop(self):
        """Stop the bot."""
        if not self.is_running:
            return

        self._stop_event.set()
        self.is_running = False
        self.is_paused = False

        self._log("🛑 Bot Agent STOPPED", 'info')

    def pause(self):
        """Pause the bot (stops scanning but keeps state)."""
        self.is_paused = True
        self._log("⏸️ Bot Agent PAUSED", 'info')

    def resume(self):
        """Resume the bot."""
        self.is_paused = False
        self._log("▶️ Bot Agent RESUMED", 'info')

    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        self._log("Starting pattern monitoring loop...")

        while not self._stop_event.is_set():
            try:
                if self.is_paused:
                    time.sleep(1)
                    continue

                # Check market hours
                if self.config['market_hours_only']:
                    now = datetime.now().time()
                    from datetime import time as dt_time
                    market_open = dt_time(9, 15)
                    market_close = dt_time(15, 30)
                    if not (market_open <= now <= market_close):
                        self._log("Outside market hours, waiting...", 'info')
                        # Sleep until next check but remain interruptible
                        self._stop_event.wait(60)
                        continue

                # Check trade limit
                if self.trades_today >= self.config['max_trades_per_day']:
                    self._log(f"Daily trade limit reached ({self.trades_today})", 'warning')
                    self._stop_event.wait(300)
                    continue

                # Run scan
                self._scan_market()
                self.last_scan_time = datetime.now()

                # Wait for next scan interval
                self._stop_event.wait(self.config['scan_interval'])

            except Exception as e:
                self._log(f"Monitor error: {e}", 'error')
                self._stop_event.wait(30)

    def _scan_market(self):
        """Perform a market scan for patterns."""
        symbol = self.config['symbol']
        self._log(f"🔍 Scanning {symbol} for patterns...")

        try:
            # Fetch candle data
            candles, close_prices = self._fetch_candle_data(symbol)

            if not candles or len(candles) < 3:
                self._log("Insufficient candle data", 'warning')
                return

            all_signals = []

            # 1. Candlestick Pattern Detection
            if self.config['candlestick_patterns_enabled']:
                candle_patterns = CandlestickPatternDetector.detect_all(candles)
                for p in candle_patterns:
                    if p['pattern'] in self.config.get('enabled_candlestick_patterns', []):
                        p['type'] = 'candlestick'
                        all_signals.append(p)

            # 2. Chart Pattern Matching (image-based)
            if self.config['chart_patterns_enabled'] and close_prices:
                chart_matches = self.chart_matcher.match_pattern(close_prices)
                for m in chart_matches:
                    if m['pattern'] in self.config.get('enabled_chart_patterns', []):
                        m['type'] = 'chart'
                        all_signals.append(m)

            # 3. VWAP Strategy Evaluation
            vwap_enabled = (self.config.get('vwap_rejection_enabled', False)
                            or self.config.get('pullback_failure_enabled', False))
            if vwap_enabled:
                # Use the same candles (intraday data) for VWAP evaluation
                intraday = self._get_intraday_candles(candles)
                if len(intraday) >= 5:
                    vwap_signals = self.vwap_engine.evaluate(intraday)
                    for vs in vwap_signals:
                        all_signals.append(vs)

            # 4. Apply additional filters (skip VWAP signals – they have their own logic)
            pattern_signals = [s for s in all_signals if s.get('type') != 'vwap_strategy']
            vwap_sigs = [s for s in all_signals if s.get('type') == 'vwap_strategy']

            filtered_signals = self._apply_filters(pattern_signals, candles, close_prices)
            filtered_signals.extend(vwap_sigs)  # VWAP signals pass through unfiltered

            # Store detected patterns
            self.detected_patterns = filtered_signals

            if filtered_signals:
                # Get strongest signal
                best = max(filtered_signals, key=lambda x: x.get('strength', 0))

                self._log(
                    f"📊 Pattern detected: {best['pattern']} "
                    f"({best['signal']}, strength: {best.get('strength', 0)}%)",
                    'signal'
                )

                # Notify via callback
                if self.on_signal:
                    try:
                        self.on_signal(best)
                    except Exception:
                        pass

                # Auto-execute check
                should_execute = False
                if best.get('type') == 'vwap_strategy':
                    should_execute = self.config.get('vwap_auto_execute', False)
                else:
                    should_execute = (self.config['auto_execute']
                                      and best.get('strength', 0) >= self.config['min_confidence'])

                if should_execute:
                    self._execute_signal(best, candles[-1])
            else:
                self._log(f"No actionable patterns found for {symbol}", 'info')

        except Exception as e:
            self._log(f"Scan error: {e}", 'error')

    def _fetch_candle_data(self, symbol: str) -> Tuple[List[CandleStick], List[float]]:
        """Fetch recent OHLCV candle data for the symbol."""
        candles = []
        close_prices = []

        # Map symbol to yfinance ticker
        ticker_map = {
            'NIFTY': '^NSEI',
            'BANKNIFTY': '^NSEBANK',
            'SENSEX': '^BSESN',
            'FINNIFTY': '^CNXFIN',
        }

        ticker_symbol = ticker_map.get(symbol, '^NSEI')

        if not HAS_YFINANCE:
            self._log("yfinance not available for data fetch", 'error')
            return candles, close_prices

        try:
            ticker = yf.Ticker(ticker_symbol)

            # Get intraday data (5-minute candles for last 5 days)
            hist = ticker.history(period="5d", interval="5m")

            if hist.empty:
                # Fallback to daily data
                hist = ticker.history(period="60d")

            if not hist.empty:
                for idx, row in hist.iterrows():
                    cs = CandleStick(
                        open_p=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        volume=float(row.get('Volume', 0)),
                        timestamp=str(idx)
                    )
                    candles.append(cs)
                    close_prices.append(float(row['Close']))

            self._log(f"Fetched {len(candles)} candles for {symbol}", 'info')

        except Exception as e:
            self._log(f"Data fetch error: {e}", 'error')

        return candles, close_prices

    def _get_intraday_candles(self, candles: List[CandleStick]) -> List[CandleStick]:
        """Filter candles to only today's intraday session (for VWAP calculation).

        VWAP resets each day, so we need only today's candles starting from
        market open (09:15 IST).
        """
        today_str = datetime.now().strftime('%Y-%m-%d')
        intraday = []
        for c in candles:
            # Timestamp is a string from yfinance like '2026-03-27 09:15:00+05:30'
            if today_str in c.timestamp:
                intraday.append(c)

        # If no today candles found (market closed / weekend), return last day's data
        if not intraday and candles:
            # Get the most recent day's candles
            last_ts = candles[-1].timestamp[:10] if candles[-1].timestamp else ''
            if last_ts:
                intraday = [c for c in candles if last_ts in c.timestamp]

        return intraday if intraday else candles

    def _handle_vwap_alert(self, alert: Dict):
        """Handle an alert from the VWAP strategy engine."""
        if self.on_vwap_alert:
            try:
                self.on_vwap_alert(alert)
            except Exception:
                pass

    def _apply_filters(self, signals: List[Dict], candles: List[CandleStick],
                       close_prices: List[float]) -> List[Dict]:
        """Apply additional technical filters to detected signals."""
        if not signals:
            return []

        filtered = []

        # Calculate RSI if needed
        rsi = None
        if self.config['rsi_filter_enabled'] and len(close_prices) >= 14:
            rsi = self._calculate_rsi(close_prices)

        # Calculate MA if needed
        ma_20 = None
        if self.config['trend_filter_enabled'] and len(close_prices) >= 20:
            ma_20 = sum(close_prices[-20:]) / 20

        current_price = close_prices[-1] if close_prices else 0

        for signal in signals:
            include = True

            # RSI filter
            if self.config['rsi_filter_enabled'] and rsi is not None:
                if signal['signal'] == 'BUY' and rsi > self.config['rsi_overbought']:
                    # Don't buy when overbought
                    include = False
                    self._log(f"Filtered {signal['pattern']}: RSI={rsi:.1f} overbought", 'info')
                elif signal['signal'] == 'SELL' and rsi < self.config['rsi_oversold']:
                    # Don't sell when oversold
                    include = False
                    self._log(f"Filtered {signal['pattern']}: RSI={rsi:.1f} oversold", 'info')

            # Trend alignment filter
            if self.config['trend_filter_enabled'] and ma_20 is not None:
                if signal['signal'] == 'BUY' and current_price < ma_20 * 0.995:
                    # Reduce strength for counter-trend buys
                    signal['strength'] = max(signal['strength'] - 15, 0)
                elif signal['signal'] == 'SELL' and current_price > ma_20 * 1.005:
                    # Reduce strength for counter-trend sells
                    signal['strength'] = max(signal['strength'] - 15, 0)

            # Minimum confidence check
            if signal.get('strength', 0) < self.config['min_confidence']:
                include = False

            if include:
                filtered.append(signal)

        return filtered

    @staticmethod
    def _calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI from price series."""
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _execute_signal(self, signal: Dict, last_candle: CandleStick):
        """Execute a trade based on the detected signal."""
        # Cooldown check
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < self.trade_cooldown:
                self._log(
                    f"Trade cooldown: {int(self.trade_cooldown - elapsed)}s remaining",
                    'warning'
                )
                return

        if not self.trader or not self.gui:
            self._log("Trader/GUI not connected - signal only mode", 'warning')
            return

        try:
            symbol = self.config['symbol']
            pattern = signal['pattern']
            direction = signal['signal']  # 'BUY' or 'SELL'
            opt_type = 'CE' if direction == 'BUY' else 'PE'
            lots = self.config['lots']

            # Get nearest ATM strike
            current_price = last_candle.close
            atm_strike = round(current_price / 50) * 50

            # Get current expiry from GUI
            expiry = ""
            if hasattr(self.gui, 'selected_expiry'):
                expiry = self.gui.selected_expiry.get()

            if not expiry:
                self._log("No expiry selected - cannot execute", 'error')
                return

            # Get lot size
            lot_size = 0
            for idx_key, idx_info in self.trader.indices.items():
                if idx_info['name'] == symbol:
                    lot_size = idx_info['lot_size']
                    break

            quantity = lots * lot_size

            trade_info = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'symbol': symbol,
                'strike': atm_strike,
                'opt_type': opt_type,
                'direction': 'BUY',  # Always BUY the option
                'quantity': quantity,
                'lots': lots,
                'pattern': pattern,
                'signal': direction,
                'strength': signal.get('strength', 0),
                'expiry': expiry
            }

            self._log(
                f"🚀 EXECUTING: BUY {symbol} {atm_strike} {opt_type} x{lots} lots "
                f"| Pattern: {pattern} ({signal.get('strength', 0)}%)",
                'trade'
            )

            # Use GUI's place_order_async for actual execution
            product_code = "I" if self.config['product_type'] == "INTRADAY" else "D"

            # Execute in background via GUI method
            threading.Thread(
                target=self.gui._place_order_async,
                args=(symbol, expiry, str(atm_strike), opt_type, quantity,
                      'BUY', self.config['order_type'], None, self.config['product_type']),
                daemon=True
            ).start()

            self.trades_today += 1
            self.last_trade_time = datetime.now()

            if self.on_trade:
                try:
                    self.on_trade(trade_info)
                except Exception:
                    pass

        except Exception as e:
            self._log(f"Trade execution error: {e}", 'error')

    def get_status(self) -> Dict:
        """Get current bot status."""
        vwap_state = self.vwap_engine.get_state_summary()
        return {
            'running': self.is_running,
            'paused': self.is_paused,
            'trades_today': self.trades_today,
            'max_trades': self.config['max_trades_per_day'],
            'last_scan': self.last_scan_time.strftime('%H:%M:%S') if self.last_scan_time else 'Never',
            'patterns_detected': len(self.detected_patterns),
            'symbol': self.config['symbol'],
            'auto_execute': self.config['auto_execute'],
            'scan_interval': self.config['scan_interval'],
            'vwap_s1_state': vwap_state['s1_state'],
            'vwap_s2_state': vwap_state['s2_state'],
        }

    def add_reference_image(self, image_path: str, name: str, signal: str,
                            description: str = "") -> bool:
        """Add a reference chart image as a training pattern.

        The image is analyzed to extract the price pattern shape, which is
        stored as a normalized sequence for future matching.
        """
        if not HAS_PIL:
            self._log("PIL (Pillow) not installed - cannot process images", 'error')
            return False

        sequence = self.chart_matcher.extract_pattern_from_image(image_path)
        if sequence is None or len(sequence) < 5:
            self._log(f"Could not extract pattern from: {image_path}", 'error')
            return False

        # Copy image to patterns directory
        import shutil
        dest = os.path.join(self.chart_matcher.reference_dir, os.path.basename(image_path))
        if os.path.abspath(image_path) != os.path.abspath(dest):
            shutil.copy2(image_path, dest)

        self.chart_matcher.save_user_pattern(
            name=name,
            signal=signal,
            description=description or f"User pattern: {name}",
            price_sequence=sequence,
            image_path=dest
        )

        self._log(f"✅ Reference pattern added: {name} ({signal})", 'info')
        return True

    def manual_scan(self) -> List[Dict]:
        """Run a manual scan and return detected patterns without auto-executing."""
        saved_auto = self.config['auto_execute']
        saved_vwap_auto = self.config.get('vwap_auto_execute', False)
        self.config['auto_execute'] = False
        self.config['vwap_auto_execute'] = False

        try:
            symbol = self.config['symbol']
            candles, close_prices = self._fetch_candle_data(symbol)

            if not candles or len(candles) < 3:
                return []

            all_signals = []

            if self.config['candlestick_patterns_enabled']:
                candle_patterns = CandlestickPatternDetector.detect_all(candles)
                for p in candle_patterns:
                    p['type'] = 'candlestick'
                    all_signals.append(p)

            if self.config['chart_patterns_enabled'] and close_prices:
                chart_matches = self.chart_matcher.match_pattern(close_prices)
                for m in chart_matches:
                    m['type'] = 'chart'
                    all_signals.append(m)

            # VWAP strategies
            vwap_enabled = (self.config.get('vwap_rejection_enabled', False)
                            or self.config.get('pullback_failure_enabled', False))
            if vwap_enabled:
                intraday = self._get_intraday_candles(candles)
                if len(intraday) >= 5:
                    # Wire callbacks for manual scan
                    self.vwap_engine.on_log = self._log
                    self.vwap_engine.on_alert = self._handle_vwap_alert
                    self.vwap_engine.s1_enabled = self.config.get('vwap_rejection_enabled', True)
                    self.vwap_engine.s2_enabled = self.config.get('pullback_failure_enabled', True)
                    vwap_signals = self.vwap_engine.evaluate(intraday)
                    all_signals.extend(vwap_signals)

                    # Also log current VWAP state for visibility
                    if not vwap_signals:
                        state = self.vwap_engine.get_state_summary()
                        self._log(
                            f"📊 VWAP State: S1={state['s1_state']}, S2={state['s2_state']}",
                            'info'
                        )

            self.detected_patterns = all_signals
            return all_signals

        finally:
            self.config['auto_execute'] = saved_auto
            self.config['vwap_auto_execute'] = saved_vwap_auto
