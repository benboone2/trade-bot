from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from dateutil.parser import parse as parse_dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from connectors.base import BaseConnector, OrderSide, OrderType, Position
from .models import Base, OrderRecord


class OMS:
    """
    Order Management System — wraps a connector and persists all order
    activity to a local SQLite database.

    Responsibilities:
      - Submit orders through the connector and log them immediately
      - Sync open orders against the broker to capture fills
      - Provide a query interface for order history and portfolio state

    Pass a RiskManager via `risk=` to automatically validate every order
    before it reaches the broker.
    """

    def __init__(self, connector: BaseConnector, risk=None, db_url: str = "sqlite:///trades.db"):
        self._connector = connector
        self._risk = risk
        self._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
    ) -> OrderRecord:
        if self._risk is not None:
            # Use the explicit price if given, otherwise fetch live ask
            if limit_price:
                estimated_price = limit_price
            else:
                quote = self._connector.get_latest_quote(symbol)
                estimated_price = quote["ask_price"] or quote["bid_price"]
            approved, reason = self._risk.check_order(symbol, side, qty, estimated_price)
            if not approved:
                from risk import RiskViolationError
                raise RiskViolationError(reason)

        order = self._connector.place_order(
            symbol, side, qty, order_type, limit_price, stop_price
        )

        record = OrderRecord(
            broker_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            qty=order.qty,
            filled_qty=order.filled_qty,
            status=order.status.value,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            filled_avg_price=order.filled_avg_price,
            submitted_at=parse_dt(order.submitted_at),
            filled_at=parse_dt(order.filled_at) if order.filled_at else None,
        )

        with self._Session() as session:
            session.add(record)
            session.commit()
            session.refresh(record)

        return record

    def cancel_order(self, broker_id: str) -> bool:
        success = self._connector.cancel_order(broker_id)
        if success:
            with self._Session() as session:
                record = session.query(OrderRecord).filter_by(broker_id=broker_id).first()
                if record:
                    record.status = "cancelled"
                    record.updated_at = datetime.now(timezone.utc)
                    session.commit()
        return success

    def cancel_all_orders(self) -> list[str]:
        cancelled_ids = self._connector.cancel_all_orders()
        if cancelled_ids:
            with self._Session() as session:
                session.query(OrderRecord).filter(
                    OrderRecord.broker_id.in_(cancelled_ids),
                ).update(
                    {"status": "cancelled", "updated_at": datetime.now(timezone.utc)},
                    synchronize_session=False,
                )
                session.commit()
        return cancelled_ids

    # ------------------------------------------------------------------
    # Sync — poll broker and update local records
    # ------------------------------------------------------------------

    def sync_orders(self) -> int:
        """
        Checks all locally pending/partially-filled orders against the broker
        and updates their status. Returns the number of records updated.
        """
        with self._Session() as session:
            pending = (
                session.query(OrderRecord)
                .filter(OrderRecord.status.in_(["pending", "partially_filled"]))
                .all()
            )

            updated = 0
            for record in pending:
                try:
                    order = self._connector.get_order(record.broker_id)
                    record.status = order.status.value
                    record.filled_qty = order.filled_qty
                    record.filled_avg_price = order.filled_avg_price
                    record.updated_at = datetime.now(timezone.utc)
                    if order.filled_at:
                        record.filled_at = parse_dt(order.filled_at)
                    updated += 1
                except Exception:
                    pass

            session.commit()

        return updated

    # ------------------------------------------------------------------
    # Positions (live from broker)
    # ------------------------------------------------------------------

    def get_positions(self) -> list[Position]:
        return self._connector.get_positions()

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._connector.get_position(symbol)

    # ------------------------------------------------------------------
    # Order history (from local DB)
    # ------------------------------------------------------------------

    def get_order_history(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[OrderRecord]:
        with self._Session() as session:
            q = session.query(OrderRecord).order_by(OrderRecord.submitted_at.desc())
            if symbol:
                q = q.filter(OrderRecord.symbol == symbol)
            if status:
                q = q.filter(OrderRecord.status == status)
            records = q.limit(limit).all()
            session.expunge_all()
            return records

    def get_open_orders(self, symbol: Optional[str] = None) -> list[OrderRecord]:
        return self.get_order_history(symbol=symbol, status="pending")

    # ------------------------------------------------------------------
    # Portfolio summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        acct = self._connector.get_account()
        positions = self._connector.get_positions()

        with self._Session() as session:
            total_orders = session.query(OrderRecord).count()
            filled_orders = (
                session.query(OrderRecord).filter_by(status="filled").count()
            )

        unrealized_pl = sum(p.unrealized_pl for p in positions)

        return {
            "cash": acct.cash,
            "portfolio_value": acct.portfolio_value,
            "buying_power": acct.buying_power,
            "equity": acct.equity,
            "open_positions": len(positions),
            "unrealized_pl": unrealized_pl,
            "total_orders_logged": total_orders,
            "filled_orders": filled_orders,
        }
