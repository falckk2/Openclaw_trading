"""Grid trading strategy — buy low/sell high in price bands."""

import uuid
from dataclasses import dataclass

from ..base import Strategy, StrategyConfig
from ..signal import Signal
from ...data.dataclasses import Candle


@dataclass
class GridConfig:
    """Configuration for grid trading strategy."""
    symbol: str
    grid_size: int = 5
    price_range_pct: float = 0.05  # ±5% from center price
    order_quantity: float = 0.001
    center_price: float | None = None  # None = use current price


class GridStrategy(Strategy):
    """Grid trading: places buy/sell orders at evenly spaced price levels."""

    def __init__(self, config: GridConfig):
        self._config = config
        self._grid_levels: list[float] = []
        self._placed_orders: dict[str, str] = {}  # level -> order_id

    @property
    def name(self) -> str:
        return "grid"

    @property
    def required_features(self) -> list[str]:
        return ["close", "high", "low"]

    def validate(self) -> bool:
        return (
            self._config.grid_size > 0
            and self._config.order_quantity > 0
            and 0 < self._config.price_range_pct < 1
        )

    def _build_grid(self, center_price: float) -> list[float]:
        """Build evenly-spaced grid levels."""
        half_range = center_price * self._config.price_range_pct
        step = (2 * half_range) / (self._config.grid_size - 1)
        return [
            center_price - half_range + i * step
            for i in range(self._config.grid_size)
        ]

    async def generate_signal(
        self, candles: list[Candle], position: object | None = None
    ) -> Signal | None:
        """
        Grid strategy doesn't generate single signals —
        it manages a grid of orders. Returns None; use grid management instead.
        """
        if not candles:
            return None

        current_price = candles[-1].close

        # Build or rebuild grid
        center = self._config.center_price or current_price
        self._grid_levels = self._build_grid(center)

        # Check for buy/sell signals at grid boundaries
        lowest_level = min(self._grid_levels)
        highest_level = max(self._grid_levels)

        if current_price <= lowest_level * 1.001:  # near lower grid line → buy
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="buy",
                confidence=0.7,
                entry_price=lowest_level,
                metadata={"grid_level": lowest_level, "type": "grid_buy"},
            )

        if current_price >= highest_level * 0.999:  # near upper grid line → sell
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="sell",
                confidence=0.7,
                entry_price=highest_level,
                metadata={"grid_level": highest_level, "type": "grid_sell"},
            )

        return Signal.hold(self.name, self._config.symbol, confidence=0.5)