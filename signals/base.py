from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from connectors.base import OrderSide


@dataclass
class Signal:
    symbol: str
    side: OrderSide
    confidence: float          # 0.0 – 1.0
    reason: str                # human-readable explanation of why signal fired
    suggested_qty: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __str__(self) -> str:
        qty = f"  qty={self.suggested_qty}" if self.suggested_qty else ""
        return (
            f"[{self.timestamp.strftime('%H:%M:%S')}] {self.side.value.upper()} {self.symbol}"
            f"  confidence={self.confidence:.0%}{qty}  reason={self.reason}"
        )


class BaseSignal(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'RSI(14)' or 'MA(20,50)'."""
        ...

    @abstractmethod
    def evaluate(self, symbol: str) -> Optional[Signal]:
        """
        Evaluate the signal for a symbol.
        Returns a Signal if conditions are met, None otherwise.
        """
        ...
