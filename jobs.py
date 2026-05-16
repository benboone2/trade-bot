"""
Core job functions shared by main.py (manual) and scheduler.py (automated).
"""

from decimal import Decimal

from connectors import AlpacaConnector
from connectors.base import OrderSide, OrderType
from oms import OMS
from risk import RiskManager
from signals import MACrossoverSignal, RSISignal, SignalEngine

WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

DEFAULT_QTY = Decimal("1")
MIN_CONFIDENCE = 0.1


def build_components():
    """Initialize and return (connector, risk, oms, engine)."""
    connector = AlpacaConnector()
    risk = RiskManager(connector)
    oms = OMS(connector, risk=risk)
    signals = [
        RSISignal(connector, period=14, oversold=30, overbought=70),
        MACrossoverSignal(connector, fast_period=20, slow_period=50),
    ]
    engine = SignalEngine(
        signals=signals,
        watchlist=WATCHLIST,
        oms=oms,
        default_qty=DEFAULT_QTY,
        min_confidence=MIN_CONFIDENCE,
    )
    return connector, risk, oms, engine


def is_market_open(connector: AlpacaConnector) -> bool:
    quote = connector.get_latest_quote("AAPL")
    return quote["ask_price"] is not None and quote["ask_price"] > 0


def run_signal_scan(connector, risk, oms, engine, execute: bool = False):
    """Evaluate signals and optionally place orders. Returns list of results."""
    rs = risk.get_status()

    if rs["halted"]:
        print(f"  TRADING HALTED: {rs['halt_reason']}")
        return []

    # Clean up any leftover open orders before scanning
    open_orders = connector.get_open_orders()
    if open_orders:
        print(f"  Cancelling {len(open_orders)} leftover open order(s)...")
        oms.cancel_all_orders()

    print(f"  Scanning {len(WATCHLIST)} symbols...")
    results = engine.run_once(execute=execute)

    if not results:
        print("  No signals fired.")
    else:
        for signal, order in results:
            order_str = (
                f"    → order {order.broker_id} [{order.status}]"
                if order
                else "    → no order placed"
            )
            print(f"  {signal}")
            print(order_str)

    return results


def run_sync(oms: OMS):
    """Sync pending orders against the broker. Returns count updated."""
    updated = oms.sync_orders()
    if updated:
        print(f"  Synced {updated} order(s)")
    return updated


def print_eod_report(oms: OMS, risk):
    """Print end-of-day account and position summary."""
    summary = oms.get_summary()
    rs = risk.get_status()
    positions = oms.get_positions()

    print(f"  Equity:       ${summary['equity']:,.2f}")
    print(f"  Cash:         ${summary['cash']:,.2f}")
    print(f"  Unrealized P&L: ${summary['unrealized_pl']:,.2f}")
    print(f"  Drawdown:     {rs['drawdown_pct']:.2%}")
    print(f"  Daily loss:   {rs['daily_loss_pct']:.2%}")

    if positions:
        print("  Positions:")
        for pos in positions:
            print(f"    {pos.symbol:6} {pos.qty} @ ${pos.avg_entry_price}  P&L: ${pos.unrealized_pl:.2f}")
    else:
        print("  No open positions")

    history = oms.get_order_history(limit=10)
    if history:
        print("  Today's orders:")
        for h in history:
            filled_str = f" @ ${h.filled_avg_price}" if h.filled_avg_price else ""
            print(f"    {h.submitted_at.strftime('%H:%M:%S')}  {h.side:4} {h.qty} {h.symbol} [{h.status}]{filled_str}")
