from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broker_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)        # buy | sell
    order_type: Mapped[str] = mapped_column(String, nullable=False)  # market | limit | stop | stop_limit
    qty: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    filled_qty: Mapped[Decimal] = mapped_column(Numeric, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    filled_avg_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<OrderRecord {self.broker_id} {self.side} {self.qty} {self.symbol}"
            f" [{self.status}]>"
        )
