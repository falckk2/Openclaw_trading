"""Live execution loop test — end-to-end with real market data (paper trading)."""

import asyncio
import sys

# Ensure src is on path so 'from src.X' works
sys.path.insert(0, "/root/.openclaw/workspace/blofin_trader")

from src.exchange.blofin_client import BlofinClient
from src.trading.engine import TradingEngine
from src.trading.position import Position
from src.strategies.ml.momentum import MomentumStrategy, MomentumConfig
from src.config.dataclasses import RiskConfig


async def main():
    print("=== Blofin Live Execution Loop Test ===\n")

    # 1. Connect to Blofin demo API
    client = BlofinClient(api_key="", api_secret="", demo=True, paper_trading=True)
    print("[1] Connected to Blofin demo API (paper trading)")

    # 2. Fetch real BTC-USDT candles
    candles = await client.get_candles("BTC-USDT", interval="1H", limit=100)
    print(f"[2] Fetched {len(candles)} BTC-USDT 1H candles")
    print(f"     Latest: {candles[-1].timestamp} | close={candles[-1].close:.2f}")

    # 3. Create MomentumStrategy signal
    config = MomentumConfig(symbol="BTC-USDT")
    strategy = MomentumStrategy(config)
    signal = await strategy.generate_signal(candles)
    print(f"[3] MomentumStrategy signal: action={signal.action}, confidence={signal.confidence:.4f}")
    print(f"     Metadata: {signal.metadata}")

    # 4. Use TradingEngine to open a position (paper trading)
    risk_config = RiskConfig()
    engine = TradingEngine(client, risk_config)

    # Check balance
    balance = await client.get_balance()
    print(f"\n[4] Account equity: {balance.total_equity:.2f} USDT")

    # Open position based on signal
    if signal.action in ("buy", "sell"):
        side = "long" if signal.action == "buy" else "short"
        qty = config.quantity  # 0.001 BTC
        entry_price = signal.entry_price or candles[-1].close

        position = await engine.open_position(
            symbol="BTC-USDT",
            side=side,
            qty=qty,
            price=entry_price,
        )
        print(f"     Opened {side} position: qty={qty} BTC, entry={entry_price:.2f}")
        print(f"     Position ID: {position.position_id}")
    else:
        print("     Signal is HOLD — testing engine methods with a simulated position")

    # 5. Update position with real prices
    ticker = await client.get_ticker("BTC-USDT")
    print(f"\n[5] Current BTC-USDT price: {ticker.last:.2f}")

    if engine.get_position("BTC-USDT"):
        pos = engine.get_position("BTC-USDT")
        pos.update_price(ticker.last)
        print(f"     Position updated: current_price={pos.current_price:.2f}, unrealized_pnl={pos.unrealized_pnl:.4f}")
    else:
        # Simulate a position for testing purposes (when signal is HOLD)
        print("     Creating a simulated position to test stop loss...")
        from datetime import datetime
        import uuid
        pos = Position(
            position_id=str(uuid.uuid4()),
            symbol="BTC-USDT",
            side="long",
            entry_price=candles[-1].close,
            quantity=config.quantity,
            current_price=ticker.last,
            opened_at=datetime.utcnow(),
        )
        engine._positions["BTC-USDT"] = pos
        print(f"     Simulated position: entry={pos.entry_price:.2f}, current={pos.current_price:.2f}")

    # 6. Use ATR-based stop loss to set dynamic stop
    pos = engine.get_position("BTC-USDT")
    if pos:
        stop = pos.update_stop_loss_atr(candles, multiplier=2.0, trailing=True)
        print(f"\n[6] ATR-based stop loss set: {stop:.2f} (ATR={pos._atr:.4f}, trailing=True)")
        print(f"     Stop loss distance: {pos.get_stop_loss_distance_pct():.2f}%")

        # Set take profit based on ATR
        tp = pos.set_take_profit_atr(candles, reward_multiplier=3.0)
        print(f"     ATR-based take profit: {tp:.2f}")
        print(f"     Risk/Reward ratio: {pos.get_risk_reward_ratio():.2f}")

    # 7. Verify position is tracked correctly
    print(f"\n[7] Verifying position tracking:")
    all_positions = engine.get_all_positions()
    print(f"     Open positions: {len(all_positions)}")
    for p in all_positions:
        print(f"     - {p.symbol}: {p.side} | entry={p.entry_price:.2f} | current={p.current_price:.2f} | PnL={p.unrealized_pnl:.4f}")
        print(f"       stop_loss={p.stop_loss} | take_profit={p.take_profit}")
        print(f"       stop loss triggered? {p.check_stop_loss_triggered()}")

    # 8. Close the position
    pos = engine.get_position("BTC-USDT")
    if pos:
        print(f"\n[8] Closing position...")
        close_resp = await engine.close_position("BTC-USDT")
        print(f"     Close order: id={close_resp.order_id}, filled_qty={close_resp.filled_qty}, avg_price={close_resp.avg_price:.2f}")
        print(f"     Remaining open positions: {len(engine.get_all_positions())}")
    else:
        print("\n[8] No position to close")

    print("\n=== Test Complete ===")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())