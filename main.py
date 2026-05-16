"""
Main runner — evaluates signals against a watchlist and places orders
when the market is open. Safe to run anytime; execution is gated on
market hours.

Run with: python main.py
"""

from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

from connectors import AlpacaConnector
from oms import OMS
from risk import RiskConfig, RiskManager
from signals import RSISignal, MACrossoverSignal, SignalEngine

WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]


def is_market_open(connector: AlpacaConnector) -> bool:
    quote = connector.get_latest_quote("AAPL")
    return quote["ask_price"] is not None and quote["ask_price"] > 0


def main():
    connector = AlpacaConnector()
    risk = RiskManager(connector)
    oms = OMS(connector, risk=risk)

    # --- Cancel any leftover open orders ---
    open_orders = connector.get_open_orders()
    if open_orders:
        print(f"Cancelling {len(open_orders)} leftover open order(s)...")
        oms.cancel_all_orders()

    # --- Account snapshot ---
    summary = oms.get_summary()
    rs = risk.get_status()
    print("=== Account ===")
    print(f"  Equity:      ${summary['equity']:,.2f}")
    print(f"  Cash:        ${summary['cash']:,.2f}")
    print(f"  Drawdown:    {rs['drawdown_pct']:.2%}  (limit {rs['limits']['max_drawdown_pct']:.0%})")
    print(f"  Daily loss:  {rs['daily_loss_pct']:.2%}  (limit {rs['limits']['max_daily_loss_pct']:.0%})")

    if rs["halted"]:
        print(f"\n  TRADING HALTED: {rs['halt_reason']}")
        return

    market_open = is_market_open(connector)
    print(f"\n  Market open: {'Yes' if market_open else 'No — signals will evaluate but no orders placed'}")

    # --- Build signal engine ---
    signals = [
        RSISignal(connector, period=14, oversold=30, overbought=70),
        MACrossoverSignal(connector, fast_period=20, slow_period=50),
    ]
    engine = SignalEngine(
        signals=signals,
        watchlist=WATCHLIST,
        oms=oms,
        default_qty=Decimal("1"),
        min_confidence=0.1,
    )

    # --- Evaluate ---
    print(f"\n=== Signal Scan ({len(WATCHLIST)} symbols, {len(signals)} signals) ===")
    results = engine.run_once(execute=market_open)

    if not results:
        print("  No signals fired.")
    else:
        for signal, order in results:
            order_str = f"  → order {order.broker_id} [{order.status}]" if order else "  → no order (market closed)"
            print(f"  {signal}")
            print(order_str)

    # --- Positions ---
    print("\n=== Positions ===")
    positions = oms.get_positions()
    if positions:
        for pos in positions:
            print(f"  {pos.symbol:6} {pos.qty} @ ${pos.avg_entry_price}  P&L: ${pos.unrealized_pl:.2f}")
    else:
        print("  None")


if __name__ == "__main__":
    main()
