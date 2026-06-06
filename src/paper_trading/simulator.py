"""Paper trading engine — simulates order execution using real market data."""

import uuid
from datetime import datetime

from ..exchange.base import ExchangeClient
from .order_tracker import SimulatedFill, SimulatedPosition, SimulatedBalance, SimulatedTrade


class PaperTradingEngine:
    """
    Simulates trading without real money.
    Implements the same interface as TradingEngine so it can be swapped in (LSP).
    """

    FEE_RATE = 0.001  # 0.1% fee per trade (adjustable)

    def __init__(self, exchange: ExchangeClient, initial_balance: float = 10000.0):
        self._exchange = exchange
        self._balance = initial_balance
        self._available = initial_balance
        self._positions: dict[str, SimulatedPosition] = {}
        self._trades: list[SimulatedTrade] = []
        self._fills: list[SimulatedFill] = []

    # ── Balance ──────────────────────────────────────────────────

    def get_balance(self) -> SimulatedBalance:
        """Get current simulated balance."""
        total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        return SimulatedBalance(
            total_equity=self._balance + total_unrealized,
            available=self._available,
            used_margin=0.0,  # no margin in paper trading
            unrealized_pnl=total_unrealized,
        )

    # ── Simulated Trading ────────────────────────────────────────

    async def simulate_market_buy(self, symbol: str, qty: float) -> SimulatedFill:
        """Simulate a market buy order."""
        ticker = await self._exchange.get_ticker(symbol)
        price = ticker.ask  # use ask price for buying
        return self._execute_buy(symbol, qty, price)

    async def simulate_market_sell(self, symbol: str, qty: float) -> SimulatedFill:
        """Simulate a market sell order."""
        ticker = await self._exchange.get_ticker(symbol)
        price = ticker.bid  # use bid price for selling
        return self._execute_sell(symbol, qty, price)

    async def simulate_limit_buy(self, symbol: str, qty: float, price: float) -> SimulatedFill:
        """Simulate a limit buy order (executes immediately at limit price)."""
        return self._execute_buy(symbol, qty, price)

    async def simulate_limit_sell(self, symbol: str, qty: float, price: float) -> SimulatedFill:
        """Simulate a limit sell order (executes immediately at limit price)."""
        return self._execute_sell(symbol, qty, price)

    def _execute_buy(self, symbol: str, qty: float, price: float) -> SimulatedFill:
        """Execute a simulated buy."""
        cost = qty * price
        fee = cost * self.FEE_RATE

        if self._available < cost + fee:
            raise ValueError(f"Insufficient balance: need {cost + fee}, have {self._available}")

        self._available -= (cost + fee)

        fill = SimulatedFill(
            order_id=f"paper_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            side="buy",
            price=price,
            quantity=qty,
            fee=fee,
        )
        self._fills.append(fill)

        # Update or create position
        if symbol in self._positions:
            pos = self._positions[symbol]
            total_qty = pos.quantity + qty
            pos.entry_price = (pos.entry_price * pos.quantity + price * qty) / total_qty
            pos.quantity = total_qty
        else:
            self._positions[symbol] = SimulatedPosition(
                position_id=f"paper_pos_{uuid.uuid4().hex[:8]}",
                symbol=symbol,
                side="long",
                entry_price=price,
                quantity=qty,
                current_price=price,
            )

        return fill

    def _execute_sell(self, symbol: str, qty: float, price: float) -> SimulatedFill:
        """Execute a simulated sell."""
        pos = self._positions.get(symbol)
        if not pos or pos.quantity < qty:
            raise ValueError(f"Cannot sell {qty} of {symbol}: only {pos.quantity if pos else 0} available")

        revenue = qty * price
        fee = revenue * self.FEE_RATE
        pnl = (price - pos.entry_price) * qty - fee

        fill = SimulatedFill(
            order_id=f"paper_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            side="sell",
            price=price,
            quantity=qty,
            fee=fee,
        )
        self._fills.append(fill)

        # Update balance
        self._available += (revenue - fee)
        self._balance += pnl

        # Update or close position
        pos.quantity -= qty
        if pos.quantity <= 0:
            del self._positions[symbol]

        # Record trade
        trade = SimulatedTrade(
            trade_id=f"paper_trade_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            side="sell",
            quantity=qty,
            entry_price=pos.entry_price,
            exit_price=price,
            pnl=pnl,
            fee=fee,
            opened_at=pos.opened_at,
            closed_at=datetime.utcnow(),
        )
        self._trades.append(trade)

        return fill

    # ── Position Queries ──────────────────────────────────────────

    def get_position(self, symbol: str) -> SimulatedPosition | None:
        """Get simulated position by symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> list[SimulatedPosition]:
        """Get all open simulated positions."""
        return list(self._positions.values())

    def get_trade_history(self) -> list[SimulatedTrade]:
        """Get all completed trades."""
        return self._trades

    async def update_position_prices(self) -> None:
        """Update current prices for all positions from exchange."""
        for symbol, position in self._positions.items():
            ticker = await self._exchange.get_ticker(symbol)
            position.current_price = ticker.last
            if position.side == "long":
                position.unrealized_pnl = (ticker.last - position.entry_price) * position.quantity
            else:
                position.unrealized_pnl = (position.entry_price - ticker.last) * position.quantity

    # ── LSP compatibility — same interface as TradingEngine ────────

    async def open_position(self, symbol: str, side: str, qty: float, price: float | None = None):
        """Open a simulated position (LSP-compatible with TradingEngine)."""
        if side == "long":
            return await self.simulate_market_buy(symbol, qty) if price is None else await self.simulate_limit_buy(symbol, qty, price)
        else:
            return await self.simulate_market_sell(symbol, qty) if price is None else await self.simulate_limit_sell(symbol, qty, price)

    async def close_position(self, symbol: str):
        """Close a simulated position."""
        pos = self._positions.get(symbol)
        if pos:
            return await self.simulate_market_sell(symbol, pos.quantity)

    def get_total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_total_realized_pnl(self) -> float:
        return sum(t.pnl for t in self._trades)