"""Data module dataclasses."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candle:
    """OHLCV candlestick data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Ticker:
    """Real-time ticker data."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


@dataclass
class OrderBook:
    """Order book data."""
    bids: list[tuple[float, float]]  # list of (price, quantity)
    asks: list[tuple[float, float]]