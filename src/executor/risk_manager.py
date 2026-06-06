"""Risk manager — validates signals against risk limits before execution."""

from ..config.dataclasses import RiskConfig
from ..trading.position import Position


class RiskManager:
    """
    Checks risk limits before any order is placed.
    Prevents over-exposure, over-loss, and position limit violations.
    """

    def __init__(self, config: RiskConfig):
        self._config = config

    def check_position_limits(
        self,
        symbol: str,
        qty: float,
        price: float,
        current_positions: list[Position],
        total_equity: float,
    ) -> tuple[bool, str]:
        """
        Check if placing this order would violate risk limits.

        Returns (allowed, reason)
        """
        position_value = qty * price

        # Max position size check
        max_position_value = total_equity * self._config.max_position_pct
        if position_value > max_position_value:
            return False, f"Position size {position_value} exceeds max {max_position_value}"

        # Max open positions check
        if len(current_positions) >= self._config.max_open_positions:
            # Check if we're trying to open a new symbol
            existing_symbols = {p.symbol for p in current_positions}
            if symbol not in existing_symbols:
                return False, f"Max open positions ({self._config.max_open_positions}) reached"

        return True, "OK"

    def check_daily_loss(self, unrealized_pnl: float, total_equity: float) -> tuple[bool, str]:
        """Check if daily loss limit is breached."""
        max_loss = total_equity * self._config.max_daily_loss_pct
        if unrealized_pnl < -max_loss:
            return False, f"Daily loss {unrealized_pnl} exceeds max {max_loss}"
        return True, "OK"

    def check_stop_loss(
        self, position: Position, current_price: float
    ) -> tuple[bool, float | None]:
        """
        Check if stop loss is triggered.
        Returns (triggered, stop_price).
        """
        if position.stop_loss is None:
            return False, None

        if position.side == "long" and current_price <= position.stop_loss:
            return True, position.stop_loss
        if position.side == "short" and current_price >= position.stop_loss:
            return True, position.stop_loss

        return False, None

    def validate_signal_quantity(
        self, signal_price: float, quantity: float, total_equity: float
    ) -> tuple[bool, str]:
        """Validate that signal parameters are reasonable."""
        position_value = signal_price * quantity
        if position_value > total_equity * self._config.max_position_pct:
            return False, f"Signal position {position_value} exceeds {self._config.max_position_pct * 100}% of equity"
        if quantity <= 0:
            return False, "Quantity must be positive"
        return True, "OK"