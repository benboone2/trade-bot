from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from oms.models import Base


class RiskState(Base):
    """Single-row table that persists risk manager state across restarts."""

    __tablename__ = "risk_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    peak_equity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    daily_start_equity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    daily_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    halted: Mapped[bool] = mapped_column(Boolean, default=False)
    halt_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
