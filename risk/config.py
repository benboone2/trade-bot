from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RiskConfig:
    # Single position cannot exceed this % of total equity
    max_position_pct: float = 0.10          # 10%

    # Single order cannot exceed this dollar value
    max_order_value: Decimal = Decimal("5000")

    # Total invested (sum of position market values) cannot exceed this % of equity
    max_exposure_pct: float = 0.80          # 80%

    # Kill switch: halt trading if equity drops this far from its all-time peak
    max_drawdown_pct: float = 0.10          # 10%

    # Kill switch: halt trading if equity drops this far from today's starting value
    max_daily_loss_pct: float = 0.05        # 5%
