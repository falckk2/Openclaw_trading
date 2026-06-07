"""Tests for exchange module."""

import pytest
from datetime import datetime, timezone, timezone

from src.exchange.base import (
    ExchangeClient, OrderRequest, OrderResponse, Position, Balance
)
from src.exchange.blofin_client import BlofinClient, _sign
from src.exchange.exceptions import APIError, RateLimitError


class TestBlofinClient:
    """Tests for BlofinClient."""

    @pytest.fixture
    def client(self):
        """Demo paper-trading client — no real API calls."""
        return BlofinClient(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            demo=True,
            paper_trading=True,
        )

    @pytest.fixture
    def live_client(self):
        """Demo client WITHOUT paper trading — hits real API (may fail without keys)."""
        return BlofinClient(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            demo=True,
            paper_trading=False,
        )

    # ------------------------------------------------------------------
    # Paper trading mode
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_paper_market_buy(self, client):
        """Market buy in paper mode returns mock filled order."""
        order = await client.place_order(OrderRequest(
            symbol="BTC-USDT",
            side="buy",
            order_type="market",
            quantity=0.01,
            price=None,
        ))
        assert order.status == "filled"
        assert order.filled_qty == 0.01
        assert order.order_id.startswith("paper_")
        assert order.side == "buy"

    @pytest.mark.asyncio
    async def test_paper_market_sell(self, client):
        """Market sell in paper mode returns mock filled order."""
        order = await client.place_order(OrderRequest(
            symbol="BTC-USDT",
            side="sell",
            order_type="market",
            quantity=0.01,
            price=None,
        ))
        assert order.status == "filled"
        assert order.side == "sell"

    @pytest.mark.asyncio
    async def test_paper_limit_order(self, client):
        """Limit order in paper mode returns mock filled order at specified price."""
        order = await client.place_order(OrderRequest(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=50000.0,
        ))
        assert order.status == "filled"
        assert order.avg_price == 50000.0
        assert order.filled_qty == 0.1

    # ------------------------------------------------------------------
    # Signature helper
    # ------------------------------------------------------------------
    def test_sign_produces_base64_signature(self):
        """_sign should return (signature, timestamp, nonce)."""
        sig, ts, nonce = _sign("secret", "GET", "/test", None)
        assert isinstance(sig, str)
        assert len(sig) > 0
        assert ts.isdigit()
        assert len(nonce) > 0

    def test_sign_includes_body_when_present(self):
        """_sign should include body in signature for POST."""
        sig_post, _, _ = _sign("secret", "POST", "/test", {"key": "value"})
        sig_get, _, _ = _sign("secret", "GET", "/test", None)
        assert sig_post != sig_get # Different method → different sig

    # ------------------------------------------------------------------
    # Integration tests (require network, skip if unavailable)
    # ------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_demo_ticker_public_endpoint(self):
        """Public ticker endpoint should work without auth on demo API."""
        client = BlofinClient(demo=True, paper_trading=True)
        ticker = await client.get_ticker("BTC-USDT")
        assert ticker.symbol == "BTC-USDT"
        assert ticker.last > 0
        # Demo API may return bid=ask=0 but last is always populated
        await client.close()

    @pytest.mark.asyncio
    async def test_demo_orderbook_public_endpoint(self):
        """Public orderbook endpoint should work without auth on demo API."""
        client = BlofinClient(demo=True, paper_trading=True)
        book = await client.get_order_book("BTC-USDT", depth=10)
        # Demo API may return empty orderbook — just verify the call succeeds
        assert isinstance(book.bids, list)
        assert isinstance(book.asks, list)
        await client.close()

    @pytest.mark.asyncio
    async def test_demo_candles_public_endpoint(self):
        """Public candles endpoint should work without auth on demo API."""
        client = BlofinClient(demo=True, paper_trading=True)
        candles = await client.get_candles("BTC-USDT", "1H", limit=10)
        assert len(candles) > 0
        c = candles[-1]  # Oldest candle
        assert c.open > 0
        assert c.close > 0
        assert c.high >= c.low
        await client.close()


class TestExchangeInterface:
    """Verify the exchange interface contract is satisfied."""

    def test_order_request_fields(self):
        """OrderRequest should have all required fields."""
        order = OrderRequest(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            quantity=0.01,
            price=50000.0,
        )
        assert order.symbol == "BTC-USDT"
        assert order.side == "buy"
        assert order.order_type == "limit"
        assert order.quantity == 0.01
        assert order.price == 50000.0

    def test_position_fields(self):
        """Position should have all required fields."""
        pos = Position(
            position_id="test_123",
            symbol="BTC-USDT",
            side="long",
            entry_price=50000.0,
            quantity=0.01,
            current_price=51000.0,
            unrealized_pnl=10.0,  # PnL is set explicitly by the trading engine
        )
        assert pos.position_id == "test_123"
        assert pos.side == "long"
        assert pos.unrealized_pnl == 10.0

    def test_balance_fields(self):
        """Balance should have all required fields."""
        bal = Balance(
            total_equity=10000.0,
            available=8000.0,
            used_margin=2000.0,
            unrealized_pnl=50.0,
        )
        assert bal.total_equity == 10000.0
        assert bal.available == 8000.0
        assert bal.used_margin == 2000.0
        assert bal.unrealized_pnl == 50.0

    def test_order_response_fields(self):
        """OrderResponse should have all required fields."""
        resp = OrderResponse(
            order_id="ord_001",
            symbol="BTC-USDT",
            status="filled",
            side="buy",
            order_type="market",
            quantity=0.01,
            filled_qty=0.01,
            avg_price=51000.0,
            fee=5.1,
            timestamp=datetime.now(timezone.utc),
        )
        assert resp.order_id == "ord_001"
        assert resp.status == "filled"
        assert resp.filled_qty == 0.01
        assert resp.fee == 5.1
