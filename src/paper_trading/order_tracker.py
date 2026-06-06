"""Simulated order tracking for paper trading."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SimulatedFill:
    """A simulated order fill."""
    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    fee: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimulatedPosition:
    """A simulated position in paper trading."""
    position_id: str
    symbol: str
    side: str
    entry_price: float
    quantity: float
    current_price: float
    unrealized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimulatedBalance:
    """Simulated account balance."""
    total_equity: float
    available: float
    used_margin: float
    unrealized_pnl: float


@dataclass
class SimulatedTrade:
    """A completed simulated trade."""
    trade_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    fee: float
    opened_at: datetime
    closed_at: datetime