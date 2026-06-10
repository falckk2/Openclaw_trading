"""RSI + Bollinger Bands strategy — combines overbought/oversold with volatility channels."""

import uuid
from dataclasses import dataclass

from ..base import Strategy
from ..signal import Signal
from ...data.dataclasses import Candle


@dataclass
class RSIBollingerConfig:
    """Configuration for RSI + Bollinger Bands strategy."""
    symbol: str
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    bb_period: int = 20
    bb_std: float = 2.0
    quantity: float = 0.001


class RSIBollingerStrategy(Strategy):
    """
    Buy when RSI is oversold AND price is near lower Bollinger Band.
    Sell when RSI is overbought AND price is near upper Bollinger Band.
    """

    @property
    def name(self) -> str:
        return "rsi_bollinger"

    @property
    def required_features(self) -> list[str]:
        return ["close", "high", "low"]

    def validate(self) -> bool:
        return (
            self._config.rsi_period > 1
            and self._config.bb_period > 1
            and 0 < self._config.rsi_oversold < self._config.rsi_overbought < 100
        )

    def _calculate_rsi(self, prices: list[float]) -> float:
        """Calculate RSI given a list of prices."""
        if len(prices) < self._config.rsi_period + 1:
            return 50.0  # neutral

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-self._config.rsi_period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-self._config.rsi_period:]]

        avg_gain = sum(gains) / len(gains) if gains else 0.001
        avg_loss = sum(losses) / len(losses) if losses else 0.001
        if avg_loss == 0:
            return 100.0  # all gains, RSI = 100

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_bollinger_bands(self, prices: list[float]) -> tuple[float, float, float]:
        """Returns (lower, middle, upper) Bollinger Bands."""
        period_prices = prices[-self._config.bb_period:]
        mean = sum(period_prices) / len(period_prices)
        variance = sum((p - mean) ** 2 for p in period_prices) / len(period_prices)
        std = variance ** 0.5
        return mean - self._config.bb_std * std, mean, mean + self._config.bb_std * std

    async def generate_signal(
        self, candles: list[Candle], position: object | None = None
    ) -> Signal | None:
        if len(candles) < max(self._config.rsi_period, self._config.bb_period) + 1:
            return Signal.hold(self.name, self._config.symbol, confidence=0.0)

        prices = [c.close for c in candles]

        rsi = self._calculate_rsi(prices)
        lower_bb, middle_bb, upper_bb = self._calculate_bollinger_bands(prices)
        current_price = prices[-1]

        # Buy: RSI oversold AND price at or below lower BB
        if rsi < self._config.rsi_oversold and current_price <= lower_bb * 1.02:
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="buy",
                confidence=0.8,
                entry_price=current_price,
                metadata={"rsi": rsi, "lower_bb": lower_bb},
            )

        # Sell: RSI overbought AND price at or above upper BB
        if rsi > self._config.rsi_overbought and current_price >= upper_bb * 0.98:
            return Signal(
                signal_id=str(uuid.uuid4()),
                strategy_name=self.name,
                symbol=self._config.symbol,
                action="sell",
                confidence=0.8,
                entry_price=current_price,
                metadata={"rsi": rsi, "upper_bb": upper_bb},
            )

        return Signal.hold(self.name, self._config.symbol, confidence=0.5)