"""Abstract exchange client interface — defines the contract for all exchange implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, AsyncIterator

from ..data.dataclasses import Candle, Ticker, OrderBook


@dataclass
class OrderRequest:
    """Request to place an order."""
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: float
    price: float | None = None


@dataclass
class OrderResponse:
    """Response from a placed order."""
    order_id: str
    symbol: str
    status: str  # "filled", "partial", "cancelled", "pending"
    side: str
    order_type: str
    quantity: float  # original order quantity
    filled_qty: float
    avg_price: float
    fee: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Position:
    """A trading position."""
    position_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    quantity: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class Balance:
    """Account balance."""
    total_equity: float
    available: float
    used_margin: float
    unrealized_pnl: float


class ExchangeClient(ABC):
    """
    Abstract exchange client.

    All exchange implementations (Blofin, Binance, etc.) must implement this interface.
    This allows the trading engine to work with any exchange without modification.
    """

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current ticker for a symbol."""

    @abstractmethod
    async def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book for a symbol."""

    @abstractmethod
    async def get_candles(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[Candle]:
        """Get historical candles."""

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place an order (market or limit)."""

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order."""

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[OrderResponse]:
        """Get all open orders, optionally filtered by symbol."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get all open positions."""

    @abstractmethod
    async def get_balance(self) -> Balance:
        """Get account balance."""

    @abstractmethod
    async def stream_candles(
        self, symbol: str, interval: str
    ) -> AsyncIterator[Candle]:
        """Stream live candles via WebSocket."""

    @abstractmethod
    async def close(self):
        """Close the client connection."""