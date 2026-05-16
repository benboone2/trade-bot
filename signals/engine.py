from decimal import Decimal
from typing import Optional

from connectors.base import OrderSide, OrderType
from oms import OMS
from oms.models import OrderRecord
from risk import RiskViolationError
from .base import BaseSignal, Signal


class SignalEngine:
    """
    Evaluates a list of signals against a watchlist and optionally routes
    hits to the OMS.

    Usage:
        engine = SignalEngine(
            signals=[RSISignal(connector), MACrossoverSignal(connector)],
            watchlist=["AAPL", "MSFT", "TSLA"],
            oms=oms,
            default_qty=Decimal("1"),
        )
        results = engine.run_once()           # evaluate only, no orders
        results = engine.run_once(execute=True)  # evaluate + place orders
    """

    def __init__(
        self,
        signals: list[BaseSignal],
        watchlist: list[str],
        oms: OMS,
        default_qty: Decimal = Decimal("1"),
        min_confidence: float = 0.0,
    ):
        self._signals = signals
        self._watchlist = watchlist
        self._oms = oms
        self._default_qty = default_qty
        self._min_confidence = min_confidence

    def run_once(self, execute: bool = False) -> list[tuple[Signal, Optional[OrderRecord]]]:
        """
        Runs every signal against every symbol in the watchlist.

        Returns a list of (Signal, OrderRecord | None). OrderRecord is None
        when execute=False or the order was blocked by risk.
        """
        results: list[tuple[Signal, Optional[OrderRecord]]] = []

        for signal in self._signals:
            for symbol in self._watchlist:
                try:
                    hit = signal.evaluate(symbol)
                except Exception as e:
                    print(f"  [{signal.name}] {symbol}: error during evaluation — {e}")
                    continue

                if hit is None:
                    continue

                if hit.confidence < self._min_confidence:
                    continue

                order_record: Optional[OrderRecord] = None

                if execute:
                    qty = hit.suggested_qty or self._default_qty
                    try:
                        order_record = self._oms.submit_order(
                            symbol=hit.symbol,
                            side=hit.side,
                            qty=qty,
                            order_type=OrderType.MARKET,
                        )
                    except RiskViolationError as e:
                        print(f"  [{signal.name}] {symbol}: blocked by risk — {e}")
                    except Exception as e:
                        print(f"  [{signal.name}] {symbol}: order failed — {e}")

                results.append((hit, order_record))

        return results
