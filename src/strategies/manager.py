"""Strategy manager — runs multiple strategies and aggregates signals."""

from typing import AsyncIterator

from .base import Strategy, StrategyConfig
from .signal import Signal
from ..data.dataclasses import Candle


class StrategyManager:
    """
    Manages multiple strategies, runs them on data, and aggregates their signals.

    SOLID:
    - OCP: add new strategy types without modifying this class
    - DIP: depends on Strategy abstraction, not concrete implementations
    """

    def __init__(self, strategies: list[Strategy]):
        self._strategies = {s.name: s for s in strategies}

    def add_strategy(self, strategy: Strategy) -> None:
        """Add a strategy to the manager."""
        self._strategies[strategy.name] = strategy

    def remove_strategy(self, name: str) -> None:
        """Remove a strategy by name."""
        self._strategies.pop(name, None)

    def get_strategy(self, name: str) -> Strategy | None:
        """Get a strategy by name."""
        return self._strategies.get(name)

    def list_strategies(self) -> list[str]:
        """List all strategy names."""
        return list(self._strategies.keys())

    async def run_strategies(
        self, candles: list[Candle], symbol: str, position: object | None = None
    ) -> list[Signal]:
        """
        Run all enabled strategies on the given candles.

        Returns a list of signals from all strategies.
        Caller is responsible for filtering/prioritizing signals.
        """
        signals = []
        for strategy in self._strategies.values():
            if not strategy.validate():
                continue
            signal = await strategy.generate_signal(candles, position)
            if signal and signal.action != "hold":
                signals.append(signal)
        return signals

    async def run_strategy(
        self, name: str, candles: list[Candle], position: object | None = None
    ) -> Signal | None:
        """Run a single strategy by name."""
        strategy = self._strategies.get(name)
        if not strategy or not strategy.validate():
            return None
        return await strategy.generate_signal(candles, position)