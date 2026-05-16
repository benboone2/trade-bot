"""
Manual runner — evaluates signals and places orders if the market is open.
Use this for one-off runs or testing. The scheduler handles automated execution.

Run with: python main.py
"""

from dotenv import load_dotenv

load_dotenv()

from jobs import build_components, is_market_open, run_signal_scan, run_sync


def main():
    connector, risk, oms, engine = build_components()

    rs = risk.get_status()
    summary = oms.get_summary()

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

    print("\n=== Signal Scan ===")
    run_signal_scan(connector, risk, oms, engine, execute=market_open)

    run_sync(oms)

    print("\n=== Positions ===")
    positions = oms.get_positions()
    if positions:
        for pos in positions:
            print(f"  {pos.symbol:6} {pos.qty} @ ${pos.avg_entry_price}  P&L: ${pos.unrealized_pl:.2f}")
    else:
        print("  None")


if __name__ == "__main__":
    main()
