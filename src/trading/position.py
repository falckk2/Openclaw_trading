"""Position dataclass for tracking open positions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Position:
    """An open trading position."""
    position_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    quantity: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    stop_loss: float | None = None
    take_profit: float | None = None

    def update_price(self, current_price: float) -> None:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = current_price
        price_diff = current_price - self.entry_price
        if self.side == "long":
            self.unrealized_pnl = price_diff * self.quantity
        else:
            self.unrealized_pnl = -price_diff * self.quantity

    def get_pnl_pct(self) -> float:
        """Get unrealized P&L as percentage of entry cost."""
        cost = self.entry_price * self.quantity
        if cost == 0:
            return 0.0
        price_diff = self.current_price - self.entry_price
        if self.side == "long":
            pnl = price_diff * self.quantity
        else:
            pnl = -price_diff * self.quantity
        return (pnl / cost) * 100