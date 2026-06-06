"""Live connection tests for Blofin demo API."""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.exchange.blofin_client import BlofinClient
from src.config.config_loader import ConfigLoader


async def check_public_endpoints(client: BlofinClient, symbol: str = "BTC-USDT"):
    """Test public market data endpoints (no auth needed)."""
    print(f"\n{'='*60}")
    print("TESTING PUBLIC ENDPOINTS")
    print(f"{'='*60}")

    # Test 1: get_ticker
    print("\n[1] get_ticker()...")
    try:
        ticker = await client.get_ticker(symbol)
        print(f"    ✅ ticker retrieved: last={ticker.last}, bid={ticker.bid}, ask={ticker.ask}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    # Test 2: get_order_book
    print("\n[2] get_order_book()...")
    try:
        book = await client.get_order_book(symbol, depth=5)
        print(f"    ✅ orderbook retrieved: {len(book.bids)} bids, {len(book.asks)} asks")
        if book.bids:
            print(f"    best bid: {book.bids[0]}")
        if book.asks:
            print(f"    best ask: {book.asks[0]}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    # Test 3: get_candles
    print("\n[3] get_candles()...")
    try:
        candles = await client.get_candles(symbol, interval="1H", limit=10)
        print(f"    ✅ candles retrieved: {len(candles)} candles")
        if candles:
            c = candles[-1]
            print(f"    latest: O={c.open}, H={c.high}, L={c.low}, C={c.close}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    return True


async def check_authenticated_endpoints(client: BlofinClient, symbol: str = "BTC-USDT"):
    """Test authenticated endpoints (requires API keys)."""
    print(f"\n{'='*60}")
    print("TESTING AUTHENTICATED ENDPOINTS")
    print(f"{'='*60}")

    # Test 4: get_balance
    print("\n[4] get_balance()...")
    try:
        balance = await client.get_balance()
        print(f"    ✅ balance retrieved: equity={balance.total_equity}, available={balance.available}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    # Test 5: get_positions
    print("\n[5] get_positions()...")
    try:
        positions = await client.get_positions()
        print(f"    ✅ positions retrieved: {len(positions)} open positions")
        for p in positions:
            print(f"    - {p.symbol} {p.side} qty={p.quantity} @ {p.entry_price}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    # Test 6: get_open_orders
    print("\n[6] get_open_orders()...")
    try:
        orders = await client.get_open_orders(symbol)
        print(f"    ✅ open orders retrieved: {len(orders)} orders")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    return True


async def check_paper_order(client: BlofinClient, symbol: str = "BTC-USDT"):
    """Test paper trading order placement."""
    print(f"\n{'='*60}")
    print("TESTING PAPER ORDER PLACEMENT")
    print(f"{'='*60}")

    from src.exchange.base import OrderRequest

    print(f"\n[7] place_market_order (paper)...")
    try:
        order_req = OrderRequest(
            symbol=symbol,
            side="buy",
            order_type="market",
            quantity=0.001,
            price=None,
        )
        resp = await client.place_order(order_req)
        print(f"    ✅ market order placed: id={resp.order_id}, filled_qty={resp.filled_qty}, avg_price={resp.avg_price}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    print(f"\n[8] place_limit_order (paper)...")
    try:
        # Get current price to place limit order nearby
        ticker = await client.get_ticker(symbol)
        limit_price = ticker.last * 0.99  # 1% below market

        order_req = OrderRequest(
            symbol=symbol,
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=limit_price,
        )
        resp = await client.place_order(order_req)
        print(f"    ✅ limit order placed: id={resp.order_id}, price={resp.avg_price}, status={resp.status}")
    except Exception as e:
        print(f"    ❌ FAILED: {type(e).__name__}: {e}")
        return False

    return True


async def main():
    print("Blofin Demo API — Live Connection Test")
    print("=" * 60)

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    raw_config = ConfigLoader.load_yaml(Path(config_path))

    api_key = raw_config.get("exchange", {}).get("api_key", "")
    api_secret = raw_config.get("exchange", {}).get("api_secret", "")
    passphrase = raw_config.get("exchange", {}).get("passphrase", "")
    demo = raw_config.get("exchange", {}).get("demo", True)
    paper = raw_config.get("exchange", {}).get("paper_trading", True)

    print(f"Demo mode: {demo}, Paper trading: {paper}")
    print(f"API key: {api_key[:8]}...")

    client = BlofinClient(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        demo=demo,
        paper_trading=paper,
    )

    symbol = raw_config.get("market", {}).get("default_symbol", "BTC-USDT")

    # Test public endpoints first
    public_ok = await check_public_endpoints(client, symbol)

    # Test authenticated endpoints
    auth_ok = await check_authenticated_endpoints(client, symbol) if api_key else False

    # Test paper order
    order_ok = await check_paper_order(client, symbol) if paper else False

    await client.close()

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Public endpoints:    {'✅ PASS' if public_ok else '❌ FAIL'}")
    print(f"  Authenticated:       {'✅ PASS' if auth_ok else '⚠️  SKIP (no keys or failed)'}")
    print(f"  Paper order:         {'✅ PASS' if order_ok else '❌ FAIL'}")

    return public_ok and order_ok


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)