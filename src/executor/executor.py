"""Signal executor — converts strategy signals into orders, with risk management."""

from ..strategies.signal import Signal
from ..exchange.base import ExchangeClient, OrderRequest
from .risk_manager import RiskManager


class SignalExecutor:
    """
    Executes signals through the trading engine, with risk checks.
    Acts as the bridge between strategy signals and order execution.
    """

    def __init__(
        self,
        exchange: ExchangeClient,
        risk_manager: RiskManager,
    ):
        self._exchange = exchange
        self._risk_manager = risk_manager

    async def execute_signal(
        self,
        signal: Signal,
        quantity: float,
        positions: list,
        total_equity: float,
    ) -> tuple[bool, str]:
        """
        Execute a signal if it passes risk checks.

        Returns (executed, reason)
        """
        # Risk checks
        if signal.entry_price is None:
            return False, "No entry price in signal"

        allowed, reason = self._risk_manager.check_position_limits(
            signal.symbol, quantity, signal.entry_price, positions, total_equity
        )
        if not allowed:
            return False, f"Risk check failed: {reason}"

        allowed, reason = self._risk_manager.validate_signal_quantity(
            signal.entry_price, quantity, total_equity
        )
        if not allowed:
            return False, f"Signal validation failed: {reason}"

        # Place order
        order_req = OrderRequest(
            symbol=signal.symbol,
            side=signal.action,  # "buy" or "sell"
            order_type="market",
            quantity=quantity,
            price=signal.entry_price,
        )

        try:
            await self._exchange.place_order(order_req)
            return True, f"Order placed: {signal.action} {quantity} {signal.symbol} @ {signal.entry_price}"
        except Exception as e:
            return False, f"Order failed: {e}"

    async def execute_close(
        self,
        symbol: str,
        positions: list,
        total_equity: float,
    ) -> tuple[bool, str]:
        """Close a position if it exists."""
        position = next((p for p in positions if p.symbol == symbol), None)
        if not position:
            return False, f"No open position for {symbol}"

        ticker = await self._exchange.get_ticker(symbol)
        price = ticker.bid if position.side == "long" else ticker.ask

        allowed, reason = self._risk_manager.check_position_limits(
            symbol, position.quantity, price, positions, total_equity
        )
        if not allowed:
            return False, f"Risk check failed for close: {reason}"

        order_req = OrderRequest(
            symbol=symbol,
            side="sell" if position.side == "long" else "buy",
            order_type="market",
            quantity=position.quantity,
            price=price,
        )

        try:
            await self._exchange.place_order(order_req)
            return True, f"Position closed: {symbol}"
        except Exception as e:
            return False, f"Close order failed: {e}"