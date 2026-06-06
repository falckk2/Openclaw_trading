"""Base strategy class — abstract interface for all trading strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .signal import Signal
from ..data.dataclasses import Candle


@dataclass
class StrategyConfig:
    """Configuration for a strategy."""
    name: str
    enabled: bool = True
    params: dict = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.
    Strategies generate signals based on market data.

    SOLID:
    - SRP: only generates trading signals
    - OCP: add new strategies without modifying this class
    - ISP: minimal interface (generate_signal, validate)
    """

    def __init__(self, config: StrategyConfig | None = None):
        self._config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the strategy."""

    @property
    def required_features(self) -> list[str]:
        """List of feature names this strategy needs (for feature engineering)."""
        return []

    @abstractmethod
    async def generate_signal(
        self,
        candles: list[Candle],
        position: object | None = None
    ) -> Signal | None:
        """
        Generate a trading signal from candle data.

        Args:
            candles: historical candles (most recent last)
            position: current position for this symbol, or None if flat

        Returns:
            Signal if action warranted, None for hold
        """

    def validate(self) -> bool:
        """
        Validate strategy configuration.
        Returns True if config is valid for running.
        """
        return True

    async def on_candle(self, candle: Candle) -> Signal | None:
        """
        Hook called on each new candle update (optional override).
        Default implementation does nothing.
        """
        return None