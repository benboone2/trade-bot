from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class AccountInfo:
    id: str
    cash: Decimal
    portfolio_value: Decimal
    buying_power: Decimal
    equity: Decimal
    paper: bool


@dataclass
class Position:
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal
    unrealized_plpc: Decimal  # percent


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: Decimal
    filled_qty: Decimal
    status: OrderStatus
    limit_price: Optional[Decimal]
    stop_price: Optional[Decimal]
    filled_avg_price: Optional[Decimal]
    submitted_at: str
    filled_at: Optional[str]


@dataclass
class Bar:
    symbol: str
    timestamp: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Optional[Decimal]


class BaseConnector(ABC):
    @abstractmethod
    def get_account(self) -> AccountInfo:
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        ...

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
    ) -> Order:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_order(self, order_id: str) -> Order:
        ...

    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        ...

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Bar]:
        ...

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> dict:
        ...
