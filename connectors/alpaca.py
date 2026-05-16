import os
from decimal import Decimal
from typing import Optional

from alpaca.data.live import StockDataStream
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import OrderType as AlpacaOrderType
from alpaca.trading.enums import QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)

from .base import (
    AccountInfo,
    Bar,
    BaseConnector,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)

_SIDE_MAP = {
    OrderSide.BUY: AlpacaOrderSide.BUY,
    OrderSide.SELL: AlpacaOrderSide.SELL,
}

_TIMEFRAME_MAP = {
    "1Min": TimeFrame(1, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
    "1Day": TimeFrame(1, TimeFrameUnit.Day),
}


def _parse_order_status(status: str) -> OrderStatus:
    return {
        "new": OrderStatus.PENDING,
        "partially_filled": OrderStatus.PARTIALLY_FILLED,
        "filled": OrderStatus.FILLED,
        "canceled": OrderStatus.CANCELLED,
        "cancelled": OrderStatus.CANCELLED,
        "rejected": OrderStatus.REJECTED,
        "pending_new": OrderStatus.PENDING,
        "accepted": OrderStatus.PENDING,
        "held": OrderStatus.PENDING,
    }.get(status, OrderStatus.PENDING)


def _to_decimal(value) -> Optional[Decimal]:
    return Decimal(str(value)) if value is not None else None


class AlpacaConnector(BaseConnector):
    """
    Alpaca Markets connector for stocks.
    Uses paper trading by default — set ALPACA_PAPER=false for live.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: Optional[bool] = None,
    ):
        self._api_key = api_key or os.environ["ALPACA_API_KEY"]
        self._secret_key = secret_key or os.environ["ALPACA_SECRET_KEY"]

        if paper is None:
            paper = os.environ.get("ALPACA_PAPER", "true").lower() != "false"
        self._paper = paper

        self._trading = TradingClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
            paper=self._paper,
        )
        self._market_data = StockHistoricalDataClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
        )
        self._stream: Optional[StockDataStream] = None

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> AccountInfo:
        acct = self._trading.get_account()
        return AccountInfo(
            id=str(acct.id),
            cash=Decimal(str(acct.cash)),
            portfolio_value=Decimal(str(acct.portfolio_value)),
            buying_power=Decimal(str(acct.buying_power)),
            equity=Decimal(str(acct.equity)),
            paper=self._paper,
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[Position]:
        return [self._map_position(p) for p in self._trading.get_all_positions()]

    def get_position(self, symbol: str) -> Optional[Position]:
        try:
            return self._map_position(self._trading.get_open_position(symbol))
        except Exception:
            return None

    def _map_position(self, p) -> Position:
        return Position(
            symbol=p.symbol,
            qty=Decimal(str(p.qty)),
            avg_entry_price=Decimal(str(p.avg_entry_price)),
            market_value=Decimal(str(p.market_value)),
            unrealized_pl=Decimal(str(p.unrealized_pl)),
            unrealized_plpc=Decimal(str(p.unrealized_plpc)),
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
    ) -> Order:
        alpaca_side = _SIDE_MAP[side]

        if order_type == OrderType.MARKET:
            req = MarketOrderRequest(
                symbol=symbol,
                qty=float(qty),
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
            )
        elif order_type == OrderType.LIMIT:
            req = LimitOrderRequest(
                symbol=symbol,
                qty=float(qty),
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                limit_price=float(limit_price),
            )
        elif order_type == OrderType.STOP:
            req = StopOrderRequest(
                symbol=symbol,
                qty=float(qty),
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                stop_price=float(stop_price),
            )
        elif order_type == OrderType.STOP_LIMIT:
            req = StopLimitOrderRequest(
                symbol=symbol,
                qty=float(qty),
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                limit_price=float(limit_price),
                stop_price=float(stop_price),
            )
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        order = self._trading.submit_order(req)
        return self._map_order(order)

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._trading.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    def cancel_all_orders(self) -> list[str]:
        """Cancel all open orders. Returns list of cancelled order IDs."""
        cancelled = self._trading.cancel_orders()
        return [str(c.id) for c in cancelled]

    def get_order(self, order_id: str) -> Order:
        return self._map_order(self._trading.get_order_by_id(order_id))

    def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol] if symbol else None)
        return [self._map_order(o) for o in self._trading.get_orders(req)]

    def _map_order(self, o) -> Order:
        return Order(
            id=str(o.id),
            symbol=o.symbol,
            side=OrderSide(o.side.value),
            order_type=OrderType(o.type.value),
            qty=Decimal(str(o.qty)),
            filled_qty=Decimal(str(o.filled_qty or 0)),
            status=_parse_order_status(o.status.value),
            limit_price=_to_decimal(o.limit_price),
            stop_price=_to_decimal(o.stop_price),
            filled_avg_price=_to_decimal(o.filled_avg_price),
            submitted_at=str(o.submitted_at),
            filled_at=str(o.filled_at) if o.filled_at else None,
        )

    # ------------------------------------------------------------------
    # Market Data
    # ------------------------------------------------------------------

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: str = "2024-01-01",
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Bar]:
        tf = _TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            raise ValueError(f"Unsupported timeframe '{timeframe}'. Choose from: {list(_TIMEFRAME_MAP)}")

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.IEX,
        )
        bars_response = self._market_data.get_stock_bars(req)
        bars = bars_response[symbol] if symbol in bars_response else []

        return [
            Bar(
                symbol=symbol,
                timestamp=str(b.timestamp),
                open=Decimal(str(b.open)),
                high=Decimal(str(b.high)),
                low=Decimal(str(b.low)),
                close=Decimal(str(b.close)),
                volume=int(b.volume),
                vwap=_to_decimal(b.vwap),
            )
            for b in bars
        ]

    def get_latest_quote(self, symbol: str) -> dict:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = self._market_data.get_stock_latest_quote(req)[symbol]
        return {
            "symbol": symbol,
            "ask_price": _to_decimal(quote.ask_price),
            "ask_size": quote.ask_size,
            "bid_price": _to_decimal(quote.bid_price),
            "bid_size": quote.bid_size,
            "timestamp": str(quote.timestamp),
        }

    # ------------------------------------------------------------------
    # Real-time Streaming
    # ------------------------------------------------------------------

    def get_stream(self) -> StockDataStream:
        """
        Returns a StockDataStream instance for subscribing to live quotes/trades/bars.

        Usage:
            stream = connector.get_stream()

            @stream.on_bar("AAPL")
            async def handle_bar(bar):
                print(bar)

            stream.run()
        """
        if self._stream is None:
            self._stream = StockDataStream(
                api_key=self._api_key,
                secret_key=self._secret_key,
            )
        return self._stream

    def close_stream(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
