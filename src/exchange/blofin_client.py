"""Blofin exchange client — production + demo trading support."""

import asyncio
import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from urllib.parse import urlencode

import aiohttp

from .base import ExchangeClient, OrderRequest, OrderResponse, Position, Balance
from .exceptions import APIError, NetworkError, RateLimitError, AuthenticationError
from ..data.dataclasses import Candle, Ticker, OrderBook


# -------------------------------------------------------------------------------
# URLs
# -------------------------------------------------------------------------------
_PRODUCTION_BASE = "https://openapi.blofin.com"
_DEMO_BASE = "https://demo-trading-openapi.blofin.com"
_PRODUCTION_WS = "wss://openapi.blofin.com/ws/public"
_DEMO_WS = "wss://demo-trading-openapi.blofin.com/ws/public"


# -------------------------------------------------------------------------------
# Endpoints (all relative to base URL)
# -------------------------------------------------------------------------------
# Market (public)
_MARKET_TICKER = "/api/v1/market/tickers"
_MARKET_ORDERBOOK = "/api/v1/market/orderbook"
_MARKET_CANDLES = "/api/v1/market/candles"
_MARKET_INSTRUMENTS = "/api/v1/market/instruments"

# Trading (authenticated)
_TRADE_ORDER = "/api/v1/trade/order"
_TRADE_CANCEL = "/api/v1/trade/cancel"
_TRADE_OPEN_ORDERS = "/api/v1/trade/orders_pending"
_TRADE_POSITIONS = "/api/v1/trade/positions"
_TRADE_QUERY_ORDER = "/api/v1/trade/order"
_ACCOUNT_BALANCE = "/api/v1/account/balance"


# -------------------------------------------------------------------------------
# Helper: BloFin signature
# -------------------------------------------------------------------------------
def _sign(secret: str, method: str, path: str, body: dict | None = None) -> tuple[str, str, str]:
    """Generate BloFin request signature.

    Message format: path + method + timestamp + nonce + body
    Encoding: HMAC-SHA256 → hex string → Base64

    Returns:
        (signature, timestamp, nonce) — all needed for request headers.
    """
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    body_str = json.dumps(body, separators=(",", ":")) if body else ""
    message = f"{path}{method}{timestamp}{nonce}{body_str}"
    hex_sig = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    signature = base64.b64encode(hex_sig.encode()).decode()
    return signature, timestamp, nonce


# -------------------------------------------------------------------------------
# Client
# -------------------------------------------------------------------------------
class BlofinClient(ExchangeClient):
    """BloFin REST + WebSocket client — supports both production and demo mode."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        demo: bool = True,
        paper_trading: bool = True,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        self._demo = demo
        self._paper_trading = paper_trading
        self._base = _DEMO_BASE if demo else _PRODUCTION_BASE
        self._session: aiohttp.ClientSession | None = None
        self._paper_orders: dict[str, OrderResponse] = {}  # paper trading order history

    # -----------------------------------------------------------------------
    # Session management
    # -----------------------------------------------------------------------
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # -----------------------------------------------------------------------
    # Core request helper
    # -----------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
        signed: bool = False,
    ) -> dict:
        session = await self._get_session()
        url = f"{self._base}{endpoint}"

        headers: dict[str, str] = {"Content-Type": "application/json"}

        if signed:
            signature, timestamp, nonce = _sign(
                self._api_secret, method, endpoint, body if method != "GET" else None
            )
            headers["ACCESS-KEY"] = self._api_key
            headers["ACCESS-SIGN"] = signature
            headers["ACCESS-TIMESTAMP"] = timestamp
            headers["ACCESS-NONCE"] = nonce
            headers["ACCESS-PASSPHRASE"] = self._passphrase

        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            else:
                # Serialize body ourselves to ensure signature matches actual sent data
                body_str = json.dumps(body, separators=(",", ":")) if body else ""
                async with session.post(url, params=params, data=body_str.encode(), headers=headers) as resp:
                    return await self._handle_response(resp)
        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error: {e}")

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> dict:
        data = await resp.json()
        code = data.get("code", resp.status)
        msg = data.get("msg", "")

        if resp.status == 429 or code == 60001:
            raise RateLimitError(f"Rate limited: {msg}")
        if resp.status == 401 or code in (60002, 60009):
            raise AuthenticationError(f"Auth failed: {msg}")
        # BloFin returns code="0" for success, code="200" in some cases, or HTTP 200 with error codes
        if resp.status >= 400 or (code != "0" and code != 200 and code != 0):
            raise APIError(code, msg)

        return data

    # -----------------------------------------------------------------------
    # Market data (public)
    # -----------------------------------------------------------------------
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current ticker for a symbol (e.g. 'BTC-USDT')."""
        data = await self._request("GET", _MARKET_TICKER, params={"instId": symbol})
        tickers = data.get("data", [])
        if not tickers:
            return Ticker(symbol=symbol, bid=0, ask=0, last=0, volume=0, timestamp=datetime.now(timezone.utc))
        t = tickers[0]
        return Ticker(
            symbol=t.get("instId", symbol),
            bid=float(t.get("bid", 0)),
            ask=float(t.get("ask", 0)),
            last=float(t.get("last", 0)),
            volume=float(t.get("vol24h", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book for a symbol.

        Note: The orderbook endpoint is not available in the BloFin API.
        Returns an empty orderbook.
        """
        return OrderBook(bids=[], asks=[])

    async def get_candles(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[Candle]:
        """Get historical candlesticks.

        Args:
            symbol:   Instrument ID, e.g. 'BTC-USDT'
            interval: Candle width — '1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W', '1M'
            limit:    Max candles to return (default 100, max 100)
        """
        data = await self._request(
            "GET", _MARKET_CANDLES,
            params={"instId": symbol, "bar": interval, "limit": str(limit)},
        )
        # API returns: [ts, open, high, low, close, vol, volCcy, volQuote, confirm]
        return [
            Candle(
                timestamp=datetime.fromtimestamp(int(c[0]) / 1000),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4]),
                volume=float(c[5]),
            )
            for c in reversed(data.get("data", []))  # oldest → newest
        ]

    # -----------------------------------------------------------------------
    # Trading (authenticated)
    # -----------------------------------------------------------------------
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a market or limit order."""
        if self._paper_trading:
            # For market orders, fetch current price from market
            price = order.price
            if order.order_type == "market" or price is None:
                try:
                    ticker = await self.get_ticker(order.symbol)
                    price = float(ticker.last)
                except Exception:
                    price = 0.0
            order_id = f"paper_{uuid.uuid4().hex[:13]}"
            response = OrderResponse(
                order_id=order_id,
                symbol=order.symbol,
                status="filled",
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                filled_qty=order.quantity,
                avg_price=price,
                fee=0.0,
                timestamp=datetime.now(timezone.utc),
            )
            self._paper_orders[order_id] = response
            return response

        # For market orders: size = quantity_in_BTC * current_price (USDT notional)
        # For limit orders: size = quantity_in_BTC * 1000 (mBTC, integer)
        # The BloFin API uses integer sizes; 1 = 0.001 BTC (mBTC) for spot
        if order.order_type == "market":
            ticker = await self.get_ticker(order.symbol)
            price = float(ticker.last)
            size_value = max(int(order.quantity * price), 1)
        else:
            # Convert BTC to mBTC (1 mBTC = 0.001 BTC)
            size_value = max(int(order.quantity * 1000), 1)

        body = {
            "instId": order.symbol,
            "side": order.side,
            "orderType": order.order_type,
            "size": str(size_value),
            "marginMode": "cross",
        }
        if order.price:
            body["price"] = str(order.price)

        data = await self._request("POST", _TRADE_ORDER, body=body, signed=True)
        d = (data.get("data") or [{}])[0]  # data is a list like [{"orderId":...}]
        return OrderResponse(
            order_id=str(d.get("orderId", "")),
            symbol=order.symbol,
            status="filled" if d.get("code") == "0" else d.get("state", "pending"),
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            filled_qty=float(d.get("fillSz", order.quantity if d.get("code") == "0" else 0)),
            avg_price=float(d.get("avgPx", 0)),
            fee=float(d.get("fee", 0)),
            timestamp=datetime.fromtimestamp(int(d.get("ts", 0)) / 1000) if d.get("ts") else datetime.now(timezone.utc),
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order."""
        body = {"instId": symbol, "ordId": order_id}
        data = await self._request("POST", _TRADE_CANCEL, body=body, signed=True)
        return data.get("data", {}).get("sCode") == "0"

    async def get_open_orders(self, symbol: str | None = None) -> list[OrderResponse]:
        """Get all open (pending) orders."""
        params = {"instId": symbol} if symbol else {}
        data = await self._request("GET", _TRADE_OPEN_ORDERS, params=params, signed=True)
        return [
            OrderResponse(
                order_id=str(o.get("ordId", "")),
                symbol=o.get("instId", ""),
                status=o.get("state", ""),
                side=o.get("side", ""),
                order_type=o.get("ordType", ""),
                filled_qty=float(o.get("fillSz", 0)),
                avg_price=float(o.get("avgPx", 0)),
                fee=float(o.get("fee", 0)),
                timestamp=datetime.fromtimestamp(int(o.get("ts", 0)) / 1000),
            )
            for o in data.get("data", [])
        ]

    async def get_order_by_id(self, order_id: str) -> OrderResponse | None:
        """Get a specific order by ID. Works for both paper and live orders."""
        # Paper trading: look up in memory
        if self._paper_trading and order_id in self._paper_orders:
            return self._paper_orders[order_id]
        # Live trading: call API
        data = await self._request(
            "GET",
            _TRADE_QUERY_ORDER,
            params={"ordId": order_id},
            signed=True,
        )
        orders = data.get("data", [])
        if not orders:
            return None
        o = orders[0]
        return OrderResponse(
            order_id=str(o.get("ordId", "")),
            symbol=o.get("instId", ""),
            status=o.get("state", ""),
            side=o.get("side", ""),
            order_type=o.get("ordType", ""),
            filled_qty=float(o.get("fillSz", 0)),
            avg_price=float(o.get("avgPx", 0)),
            fee=float(o.get("fee", 0)),
            timestamp=datetime.fromtimestamp(int(o.get("ts", 0)) / 1000),
        )

    async def get_positions(self) -> list[Position]:
        """Get all open positions."""
        # Paper trading without API keys — return empty positions list
        if self._paper_trading and not self._api_key:
            return []
        data = await self._request("GET", _TRADE_POSITIONS, signed=True)
        return [
            Position(
                position_id=str(p.get("posId", "")),
                symbol=p.get("instId", ""),
                side=p.get("posSide", "long"),
                entry_price=float(p.get("entryPx", 0)),
                quantity=float(p.get("pos",0)),
                current_price=float(p.get("last",0)),
                unrealized_pnl=float(p.get("upl", 0)),
                realized_pnl=float(p.get("pl", 0)),
                opened_at=datetime.fromtimestamp(int(p.get("openTime", 0)) / 1000),
                stop_loss=float(p.get("sl",0)) if p.get("sl") not in (None, "") else None,
                take_profit=float(p.get("tp", 0)) if p.get("tp") not in (None, "") else None,
            )
            for p in data.get("data", [])
        ]

    async def get_balance(self) -> Balance:
        """Get account balance."""
        # Paper trading without API keys — return a mock balance
        if self._paper_trading and not self._api_key:
            return Balance(
                total_equity=10000.0,
                available=10000.0,
                used_margin=0.0,
                unrealized_pnl=0.0,
            )
        data = await self._request("GET", _ACCOUNT_BALANCE, signed=True)
        b = data.get("data", {})
        detail = b.get("details", [{}])[0]
        return Balance(
            total_equity=float(b.get("totalEquity", 0)),
            available=float(detail.get("available", 0)),
            used_margin=float(detail.get("orderFrozen", 0)),
            unrealized_pnl=float(detail.get("isolatedUnrealizedPnl", 0)),
        )

    # -----------------------------------------------------------------------
    # WebSocket (stub — implement later)
    # -----------------------------------------------------------------------
    async def stream_candles(self, symbol: str, interval: str) -> AsyncIterator[Candle]:
        """Stream live candles via WebSocket. Not yet implemented."""
        raise NotImplementedError("WebSocket candle streaming not yet implemented")

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
