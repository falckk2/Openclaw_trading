"""Momentum strategy — hybrid of trend momentum and mean reversion entry points."""

import uuid
from dataclasses import dataclass

from ..base import Strategy
from ..signal import Signal
from ...data.dataclasses import Candle


@dataclass
class MomentumConfig:
    """Configuration for momentum strategy."""
    symbol: str
    momentum_period: int = 10      # period for momentum calculation
    ma_short: int = 20              # short MA for entry timing
    ma_long: int = 50              # long MA for trend direction
    quantity: float = 0.001
    momentum_threshold: float = 0.01   # min momentum return to confirm trend
    entry_deviation: float = -0.5      # buy when price is N stdev below short MA
    exit_deviation: float = 0.3        # exit when deviation normalized to this


class MomentumStrategy(Strategy):
    """
    Momentum + Mean Reversion hybrid:
    - Buy when: strong upward momentum AND price pulled back to below short MA (reversion entry)
    - Sell when: strong downward momentum AND price pushed back to above short MA (reversion entry)
    - Hold when: no clear momentum or price is in neutral zone

    Combines the best of both: catches trends early (momentum) while entering at better prices (mean reversion).
    """

    def __init__(self, config: MomentumConfig):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "momentum"

    @property
    def required_features(self) -> list[str]:
        return ["close"]

    def validate(self) -> bool:
        return (
            self._config.momentum_period > 1
            and self._config.ma_short > self._config.momentum_period
            and self._config.ma_long > self._config.ma_short
            and self._config.quantity > 0
        )

    def _calculate_ma(self, prices: list[float], window: int) -> float:
        """Calculate simple moving average."""
        if len(prices) < window:
            return sum(prices) / len(prices)
        return sum(prices[-window:]) / window

    def _calculate_momentum(self, prices: list[float]) -> float:
        """Calculate momentum as percentage return over momentum_period."""
        if len(prices) < self._config.momentum_period + 1:
            return 0.0
        start_price = prices[-self._config.momentum_period - 1]
        end_price = prices[-1]
        if start_price == 0:
            return 0.0
        return (end_price - start_price) / start_price

    def _calculate_stdev(self, prices: list[float], window: int) -> float:
        """Calculate standard deviation over window."""
        if len(prices) < window:
            window = len(prices)
        recent = prices[-window:]
        mean = sum(recent) / len(recent)
        variance = sum((p - mean) ** 2 for p in recent) / len(recent)
        return variance ** 0.5

    async def generate_signal(
        self, candles: list[Candle], position: object | None = None
    ) -> Signal | None:
        min_required = self._config.ma_long + 1
        if len(candles) < min_required:
            return Signal.hold(self.name, self._config.symbol, confidence=0.0)

        prices = [c.close for c in candles]
        current_price = prices[-1]

        # Calculate components
        momentum = self._calculate_momentum(prices)
        ma_short = self._calculate_ma(prices, self._config.ma_short)
        ma_long = self._calculate_ma(prices, self._config.ma_long)
        stdev_short = self._calculate_stdev(prices, self._config.ma_short)

        # Deviation from short MA
        deviation = (current_price - ma_short) / stdev_short if stdev_short > 0 else 0

        # Trend direction: price above long MA = uptrend, below = downtrend
        trend_up = current_price > ma_long
        trend_down = current_price < ma_long

        # BUY: upward momentum confirmed + price slightly below short MA (reversion entry)
        # OR: strong uptrend with meaningful pullback
        if (
            (momentum > self._config.momentum_threshold and deviation < self._config.entry_deviation)
            or (trend_up and deviation < -1.0 and momentum > 0)
        ):
            confidence = min(0.95, abs(momentum) * 10 + abs(deviation) * 0.2)
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="buy",
                confidence=confidence,
                entry_price=current_price,
                metadata={
                    "momentum": momentum,
                    "ma_short": ma_short,
                    "ma_long": ma_long,
                    "deviation": deviation,
                },
            )

        # SELL: downward momentum confirmed + price slightly above short MA (reversion entry)
        # OR: strong downtrend with meaningful bounce
        if (
            (momentum < -self._config.momentum_threshold and deviation > -self._config.entry_deviation)
            or (trend_down and deviation > 1.0 and momentum < 0)
        ):
            confidence = min(0.95, abs(momentum) * 10 + abs(deviation) * 0.2)
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="sell",
                confidence=confidence,
                entry_price=current_price,
                metadata={
                    "momentum": momentum,
                    "ma_short": ma_short,
                    "ma_long": ma_long,
                    "deviation": deviation,
                },
            )

        return Signal.hold(self.name, self._config.symbol, confidence=abs(momentum) * 5)