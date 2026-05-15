"""
Connection test — verifies the Alpaca connector is wired up correctly.
Run with: python main.py
"""

import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

from connectors import AlpacaConnector
from connectors.base import OrderSide, OrderType


def main():
    connector = AlpacaConnector()

    print("=== Account ===")
    acct = connector.get_account()
    print(f"  ID:             {acct.id}")
    print(f"  Paper trading:  {acct.paper}")
    print(f"  Cash:           ${acct.cash:,.2f}")
    print(f"  Buying power:   ${acct.buying_power:,.2f}")
    print(f"  Portfolio value:${acct.portfolio_value:,.2f}")

    print("\n=== Positions ===")
    positions = connector.get_positions()
    if positions:
        for pos in positions:
            print(f"  {pos.symbol}: {pos.qty} shares @ ${pos.avg_entry_price} | P&L: ${pos.unrealized_pl:.2f}")
    else:
        print("  No open positions")

    print("\n=== Open Orders ===")
    orders = connector.get_open_orders()
    if orders:
        for order in orders:
            print(f"  {order.id}: {order.side.value} {order.qty} {order.symbol} [{order.status.value}]")
    else:
        print("  No open orders")

    print("\n=== Latest Quote: AAPL ===")
    quote = connector.get_latest_quote("AAPL")
    print(f"  Bid: ${quote['bid_price']} x {quote['bid_size']}")
    print(f"  Ask: ${quote['ask_price']} x {quote['ask_size']}")
    print(f"  Time: {quote['timestamp']}")

    print("\n=== Historical Bars: AAPL (last 5 days) ===")
    bars = connector.get_bars("AAPL", timeframe="1Day", start="2025-05-01", limit=5)
    for bar in bars:
        print(f"  {bar.timestamp[:10]}  O:{bar.open}  H:{bar.high}  L:{bar.low}  C:{bar.close}  Vol:{bar.volume:,}")

    # Uncomment to test a paper trade order:
    # print("\n=== Placing Test Order ===")
    # order = connector.place_order("AAPL", OrderSide.BUY, Decimal("1"), OrderType.MARKET)
    # print(f"  Order placed: {order.id} [{order.status.value}]")
    # connector.cancel_order(order.id)
    # print(f"  Order cancelled")


if __name__ == "__main__":
    main()
