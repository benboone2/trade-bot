"""
Account, portfolio, and risk status — safe to run anytime.
Run with: python status.py
"""

from dotenv import load_dotenv

load_dotenv()

from connectors import AlpacaConnector
from oms import OMS
from risk import RiskConfig, RiskManager


def main():
    connector = AlpacaConnector()
    risk = RiskManager(connector)
    oms = OMS(connector, risk=risk)

    # --- Account ---
    summary = oms.get_summary()
    print("=== Account ===")
    print(f"  Cash:           ${summary['cash']:,.2f}")
    print(f"  Equity:         ${summary['equity']:,.2f}")
    print(f"  Buying power:   ${summary['buying_power']:,.2f}")
    print(f"  Unrealized P&L: ${summary['unrealized_pl']:,.2f}")

    # --- Risk ---
    rs = risk.get_status()
    print("\n=== Risk ===")
    halted_str = f"YES — {rs['halt_reason']}" if rs["halted"] else "No"
    print(f"  Halted:         {halted_str}")
    print(f"  Drawdown:       {rs['drawdown_pct']:.2%}  (limit {rs['limits']['max_drawdown_pct']:.0%})")
    print(f"  Daily loss:     {rs['daily_loss_pct']:.2%}  (limit {rs['limits']['max_daily_loss_pct']:.0%})")
    print(f"  Peak equity:    ${rs['peak_equity']:,.2f}")
    print(f"  Limits:  order max ${rs['limits']['max_order_value']:,.0f}"
          f"  |  position {rs['limits']['max_position_pct']:.0%}"
          f"  |  exposure {rs['limits']['max_exposure_pct']:.0%}")

    # --- Positions ---
    print("\n=== Positions ===")
    positions = oms.get_positions()
    if positions:
        for pos in positions:
            print(f"  {pos.symbol:6} {pos.qty} shares @ ${pos.avg_entry_price}"
                  f"  |  P&L: ${pos.unrealized_pl:.2f} ({float(pos.unrealized_plpc):.2%})")
    else:
        print("  No open positions")

    # --- Open orders at broker ---
    print("\n=== Open Orders (Broker) ===")
    open_orders = connector.get_open_orders()
    if open_orders:
        for o in open_orders:
            limit = f"  limit ${o.limit_price}" if o.limit_price else ""
            print(f"  {o.id}  {o.side.value:4} {o.qty} {o.symbol}{limit}  [{o.status.value}]")
    else:
        print("  None")

    # --- Order history ---
    print("\n=== Order History (DB, last 20) ===")
    history = oms.get_order_history(limit=20)
    if history:
        for h in history:
            filled_str = f" @ ${h.filled_avg_price}" if h.filled_avg_price else ""
            print(f"  {h.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}  {h.side:4}"
                  f" {h.qty} {h.symbol:6} [{h.status}]{filled_str}")
    else:
        print("  No order history")

    print(f"\n  Total logged: {summary['total_orders_logged']}  |  Filled: {summary['filled_orders']}")


if __name__ == "__main__":
    main()
