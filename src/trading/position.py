"""Position dataclass for tracking open positions with dynamic stop loss."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from ..data.dataclasses import Candle


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
    # ATR-based dynamic stop loss fields
    atr_multiplier: float = 2.0      # stop distance = ATR * multiplier
    atr_period: int = 14             # ATR lookback period
    trailing_stop: bool = False      # whether to use trailing stop
    _atr: float | None = None        # cached ATR value
    _stop_reset_price: float | None = None  # price at which stop was last reset

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

    def calculate_atr(self, candles: list[Candle]) -> float:
        """
        Calculate Average True Range (ATR) from candle data.
        ATR = SMA of True Range over atr_period.

        True Range = max(
            high - low,
            |high - previous_close|,
            |low - previous_close|
        )
        """
        if len(candles) < self.atr_period + 1:
            # Not enough data for full ATR, use simplified version
            if len(candles) < 2:
                return 0.0
            return sum(c.high - c.low for c in candles[-len(candles):]) / len(candles)

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i - 1].close
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        # Use last atr_period true ranges
        recent_trs = true_ranges[-self.atr_period:]
        return sum(recent_trs) / len(recent_trs)

    def update_stop_loss_atr(
        self,
        candles: list[Candle],
        multiplier: float | None = None,
        trailing: bool = False
    ) -> float | None:
        """
        Update stop loss based on ATR.

        For long positions:
            stop = current_price - (ATR * multiplier)
        For short positions:
            stop = current_price + (ATR * multiplier)

        If trailing=True, the stop only moves in the favorable direction
        (up for longs, down for shorts).

        Returns the new stop loss price, or None if ATR couldn't be calculated.
        """
        if multiplier is None:
            multiplier = self.atr_multiplier

        atr = self.calculate_atr(candles)
        self._atr = atr

        current_price = self.current_price

        if self.side == "long":
            new_stop = current_price - (atr * multiplier)
            # Trailing stop: only raise, never lower
            if trailing and self.stop_loss is not None:
                new_stop = max(new_stop, self.stop_loss)
        else:  # short
            new_stop = current_price + (atr * multiplier)
            # Trailing stop: only lower, never raise
            if trailing and self.stop_loss is not None:
                new_stop = min(new_stop, self.stop_loss)

        self.stop_loss = new_stop
        self._stop_reset_price = current_price
        self.trailing_stop = trailing
        return new_stop

    def check_stop_loss_triggered(self, price: float | None = None) -> bool:
        """
        Check if price has hit the stop loss.
        Returns True if stop loss is triggered.
        """
        if self.stop_loss is None:
            return False

        check_price = price if price is not None else self.current_price

        if self.side == "long":
            return check_price <= self.stop_loss
        else:  # short
            return check_price >= self.stop_loss

    def get_stop_loss_distance_pct(self) -> float:
        """Get stop loss distance as percentage from current price."""
        if self.stop_loss is None:
            return 0.0

        distance = abs(self.current_price - self.stop_loss)
        return (distance / self.current_price) * 100 if self.current_price > 0 else 0.0

    def set_take_profit_atr(
        self,
        candles: list[Candle],
        reward_multiplier: float = 3.0
    ) -> float | None:
        """
        Set take profit based on ATR multiples.
        TP distance = ATR * reward_multiplier (risk-based TP).

        For long: TP = entry_price + (ATR * reward_multiplier)
        For short: TP = entry_price - (ATR * reward_multiplier)
        """
        atr = self.calculate_atr(candles)
        if atr <= 0:
            return None

        if self.side == "long":
            tp = self.entry_price + (atr * reward_multiplier)
        else:
            tp = self.entry_price - (atr * reward_multiplier)

        self.take_profit = tp
        return tp

    def check_take_profit_triggered(self, price: float | None = None) -> bool:
        """Check if price has hit the take profit."""
        if self.take_profit is None:
            return False

        check_price = price if price is not None else self.current_price

        if self.side == "long":
            return check_price >= self.take_profit
        else:  # short
            return check_price <= self.take_profit

    def get_risk_reward_ratio(self) -> float | None:
        """
        Calculate risk/reward ratio based on stop loss and take profit.
        Returns None if stop loss or take profit not set.
        """
        if self.stop_loss is None or self.take_profit is None:
            return None

        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)

        if risk == 0:
            return None

        return reward / risk