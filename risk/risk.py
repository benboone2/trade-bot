from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from connectors.base import BaseConnector, OrderSide
from oms.models import Base
from .config import RiskConfig
from .models import RiskState


class RiskViolationError(Exception):
    pass


class RiskManager:
    """
    Validates orders against configurable risk limits and persists kill-switch
    state to the database so halts survive process restarts.

    Checks (in order):
      1. Trading halted (manual or automatic kill switch)
      2. Max drawdown from equity peak
      3. Max daily loss from today's starting equity
      4. Max single order value (qty * estimated price)
      5. Max single position size as % of equity
      6. Max total portfolio exposure as % of equity
    """

    def __init__(
        self,
        connector: BaseConnector,
        config: Optional[RiskConfig] = None,
        db_url: str = "sqlite:///trades.db",
    ):
        self._connector = connector
        self._config = config or RiskConfig()
        self._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)
        self._ensure_state()

    # ------------------------------------------------------------------
    # State bootstrap
    # ------------------------------------------------------------------

    def _ensure_state(self):
        """Create the risk_state row on first run."""
        with self._Session() as session:
            state = session.get(RiskState, 1)
            if state is None:
                acct = self._connector.get_account()
                state = RiskState(
                    id=1,
                    peak_equity=acct.equity,
                    daily_start_equity=acct.equity,
                    daily_start_date=date.today(),
                    halted=False,
                    halt_reason=None,
                )
                session.add(state)
                session.commit()

    def _get_state(self, session) -> RiskState:
        return session.get(RiskState, 1)

    # ------------------------------------------------------------------
    # Order validation
    # ------------------------------------------------------------------

    def check_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        estimated_price: Decimal,
    ) -> tuple[bool, str]:
        """
        Returns (approved, reason). Raises nothing — callers decide whether
        to raise or just log the rejection.
        """
        cfg = self._config
        order_value = qty * estimated_price

        with self._Session() as session:
            state = self._get_state(session)
            self._maybe_reset_daily(session, state)

            if state.halted:
                return False, f"trading halted: {state.halt_reason}"

            acct = self._connector.get_account()
            equity = acct.equity

            # Update peak equity
            if equity > state.peak_equity:
                state.peak_equity = equity
                session.commit()

            # Max drawdown kill switch
            drawdown = (state.peak_equity - equity) / state.peak_equity
            if drawdown >= Decimal(str(cfg.max_drawdown_pct)):
                reason = f"max drawdown breached ({float(drawdown):.1%} >= {cfg.max_drawdown_pct:.1%})"
                self._halt(session, state, reason)
                return False, f"trading halted: {reason}"

            # Max daily loss kill switch
            daily_loss = (state.daily_start_equity - equity) / state.daily_start_equity
            if daily_loss >= Decimal(str(cfg.max_daily_loss_pct)):
                reason = f"max daily loss breached ({float(daily_loss):.1%} >= {cfg.max_daily_loss_pct:.1%})"
                self._halt(session, state, reason)
                return False, f"trading halted: {reason}"

            # Max order value
            if order_value > cfg.max_order_value:
                return False, (
                    f"order value ${order_value:,.2f} exceeds limit ${cfg.max_order_value:,.2f}"
                )

            # Max single position size
            if side == OrderSide.BUY:
                positions = self._connector.get_positions()
                existing = next((p for p in positions if p.symbol == symbol), None)
                existing_value = existing.market_value if existing else Decimal("0")
                new_position_value = existing_value + order_value
                position_pct = new_position_value / equity
                if position_pct > Decimal(str(cfg.max_position_pct)):
                    return False, (
                        f"{symbol} position would be {float(position_pct):.1%} of equity"
                        f" (limit {cfg.max_position_pct:.1%})"
                    )

                # Max total exposure
                total_exposure = sum(p.market_value for p in positions) + order_value
                exposure_pct = total_exposure / equity
                if exposure_pct > Decimal(str(cfg.max_exposure_pct)):
                    return False, (
                        f"total exposure would be {float(exposure_pct):.1%} of equity"
                        f" (limit {cfg.max_exposure_pct:.1%})"
                    )

        return True, "ok"

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    def halt(self, reason: str = "manual halt"):
        with self._Session() as session:
            state = self._get_state(session)
            self._halt(session, state, reason)

    def resume(self):
        with self._Session() as session:
            state = self._get_state(session)
            state.halted = False
            state.halt_reason = None
            state.updated_at = datetime.now(timezone.utc)
            session.commit()

    def _halt(self, session, state: RiskState, reason: str):
        state.halted = True
        state.halt_reason = reason
        state.updated_at = datetime.now(timezone.utc)
        session.commit()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        with self._Session() as session:
            state = self._get_state(session)
            acct = self._connector.get_account()
            equity = acct.equity

            drawdown = (state.peak_equity - equity) / state.peak_equity
            daily_loss = (state.daily_start_equity - equity) / state.daily_start_equity

            return {
                "halted": state.halted,
                "halt_reason": state.halt_reason,
                "equity": equity,
                "peak_equity": state.peak_equity,
                "drawdown_pct": float(drawdown),
                "daily_start_equity": state.daily_start_equity,
                "daily_loss_pct": float(daily_loss),
                "limits": {
                    "max_drawdown_pct": self._config.max_drawdown_pct,
                    "max_daily_loss_pct": self._config.max_daily_loss_pct,
                    "max_order_value": float(self._config.max_order_value),
                    "max_position_pct": self._config.max_position_pct,
                    "max_exposure_pct": self._config.max_exposure_pct,
                },
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_reset_daily(self, session, state: RiskState):
        """Reset daily starting equity at the start of each new trading day."""
        if state.daily_start_date < date.today():
            acct = self._connector.get_account()
            state.daily_start_equity = acct.equity
            state.daily_start_date = date.today()
            session.commit()
