from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from connectors.base import BaseConnector, OrderSide
from .base import BaseSignal, Signal
from .indicators import rsi, sma_series


class RSISignal(BaseSignal):
    """
    Fires a BUY when RSI drops below `oversold` and a SELL when it rises
    above `overbought`. Confidence scales linearly with how far RSI is from
    the threshold (deeper = higher confidence).
    """

    def __init__(
        self,
        connector: BaseConnector,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        timeframe: str = "1Day",
        bar_count: int = 60,
    ):
        self._connector = connector
        self._period = period
        self._oversold = oversold
        self._overbought = overbought
        self._timeframe = timeframe
        self._bar_count = bar_count

    @property
    def name(self) -> str:
        return f"RSI({self._period})"

    def evaluate(self, symbol: str) -> Optional[Signal]:
        closes = self._fetch_closes(symbol)
        if closes is None:
            return None

        try:
            value = rsi(closes, self._period)
        except ValueError:
            return None

        if value <= self._oversold:
            # Confidence: 0% at threshold, 100% at RSI=0
            confidence = min(1.0, (self._oversold - value) / self._oversold)
            return Signal(
                symbol=symbol,
                side=OrderSide.BUY,
                confidence=round(confidence, 3),
                reason=f"RSI={value:.1f} below oversold threshold {self._oversold}",
            )

        if value >= self._overbought:
            confidence = min(1.0, (value - self._overbought) / (100 - self._overbought))
            return Signal(
                symbol=symbol,
                side=OrderSide.SELL,
                confidence=round(confidence, 3),
                reason=f"RSI={value:.1f} above overbought threshold {self._overbought}",
            )

        return None

    def _fetch_closes(self, symbol: str) -> Optional[list[float]]:
        start = (datetime.now() - timedelta(days=self._bar_count * 2)).strftime("%Y-%m-%d")
        bars = self._connector.get_bars(symbol, timeframe=self._timeframe, start=start, limit=self._bar_count)
        if len(bars) < self._period + 1:
            return None
        return [float(b.close) for b in bars]


class MACrossoverSignal(BaseSignal):
    """
    Golden cross / death cross signal.

    BUY  when the fast SMA crosses above the slow SMA (golden cross).
    SELL when the fast SMA crosses below the slow SMA (death cross).

    Evaluates the last two bars to detect the crossover — no signal is
    emitted when the relationship is unchanged.
    """

    def __init__(
        self,
        connector: BaseConnector,
        fast_period: int = 20,
        slow_period: int = 50,
        timeframe: str = "1Day",
    ):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")
        self._connector = connector
        self._fast = fast_period
        self._slow = slow_period
        self._timeframe = timeframe

    @property
    def name(self) -> str:
        return f"MA({self._fast},{self._slow})"

    def evaluate(self, symbol: str) -> Optional[Signal]:
        # Need slow_period bars + 1 extra to detect the crossover
        bar_count = self._slow + 10
        start = (datetime.now() - timedelta(days=bar_count * 2)).strftime("%Y-%m-%d")
        bars = self._connector.get_bars(symbol, timeframe=self._timeframe, start=start, limit=bar_count)

        if len(bars) < self._slow + 1:
            return None

        closes = [float(b.close) for b in bars]

        fast_series = sma_series(closes, self._fast)
        slow_series = sma_series(closes, self._slow)

        # Align: both series end at the same (most recent) bar
        fast_prev, fast_curr = fast_series[-2], fast_series[-1]
        slow_prev, slow_curr = slow_series[-2], slow_series[-1]

        prev_above = fast_prev > slow_prev
        curr_above = fast_curr > slow_curr

        if not prev_above and curr_above:
            gap_pct = (fast_curr - slow_curr) / slow_curr
            confidence = min(1.0, abs(gap_pct) * 50)  # scales with spread size
            return Signal(
                symbol=symbol,
                side=OrderSide.BUY,
                confidence=round(confidence, 3),
                reason=(
                    f"Golden cross: SMA{self._fast}={fast_curr:.2f} crossed above"
                    f" SMA{self._slow}={slow_curr:.2f}"
                ),
            )

        if prev_above and not curr_above:
            gap_pct = (slow_curr - fast_curr) / slow_curr
            confidence = min(1.0, abs(gap_pct) * 50)
            return Signal(
                symbol=symbol,
                side=OrderSide.SELL,
                confidence=round(confidence, 3),
                reason=(
                    f"Death cross: SMA{self._fast}={fast_curr:.2f} crossed below"
                    f" SMA{self._slow}={slow_curr:.2f}"
                ),
            )

        return None
