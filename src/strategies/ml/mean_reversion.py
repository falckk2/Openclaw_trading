"""Mean reversion strategy — buy when price is below moving average, sell when above."""

import uuid
from dataclasses import dataclass

from ..base import Strategy
from ..signal import Signal
from ...data.dataclasses import Candle


@dataclass
class MeanReversionConfig:
    """Configuration for mean reversion strategy."""
    symbol: str
    window: int = 20  # moving average window
    std_multiplier: float = 2.0  # enter when price deviates this many stdev from MA
    exit_threshold: float = 0.5  # exit when deviation drops below this
    quantity: float = 0.001


class MeanReversionStrategy(Strategy):
    """Buy when price is significantly below its moving average, sell when above."""

    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def required_features(self) -> list[str]:
        return ["close"]

    def validate(self) -> bool:
        return self._config.window > 1 and self._config.quantity > 0

    async def generate_signal(
        self, candles: list[Candle], position: object | None = None
    ) -> Signal | None:
        if len(candles) < self._config.window:
            return Signal.hold(self.name, self._config.symbol, confidence=0.0)

        prices = [c.close for c in candles]
        recent = prices[-self._config.window:]
        mean = sum(recent) / len(recent)

        # Calculate standard deviation
        variance = sum((p - mean) ** 2 for p in recent) / len(recent)
        std = variance ** 0.5

        current_price = prices[-1]
        deviation = (current_price - mean) / std if std > 0 else 0

        # Buy when significantly below mean
        if deviation < -self._config.std_multiplier:
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="buy",
                confidence=min(0.9, abs(deviation) / self._config.std_multiplier),
                entry_price=current_price,
                metadata={"deviation": deviation, "ma": mean},
            )

        # Sell when significantly above mean or position is open and deviation normalized
        if deviation > self._config.std_multiplier:
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="sell",
                confidence=min(0.9, deviation / self._config.std_multiplier),
                entry_price=current_price,
                metadata={"deviation": deviation, "ma": mean},
            )

        return Signal.hold(self.name, self._config.symbol, confidence=abs(deviation))