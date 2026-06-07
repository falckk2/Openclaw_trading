"""Live execution loop test — end-to-end with real market data."""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.exchange.blofin_client import BlofinClient
from src.trading.engine import TradingEngine
from src.trading.position import Position
from src.strategies.ml.momentum import MomentumStrategy, MomentumConfig
from src.config.dataclasses import RiskConfig


async def main():
    print("=" * 60)
    print("LIVE EXECUTION LOOP TEST")
    print("=" * 60)

    # ── Setup ──────────────────────────────────────────────────────
    symbol = "BTC-USDT"

    client = BlofinClient(
        api_key="",           # no keys needed for paper mode
        api_secret="",
        passphrase="",
        demo=True,
        paper_trading=True,
    )

    risk_config = RiskConfig(
        max_position_pct=0.1,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_daily_loss_pct=0.05,
        max_open_positions=3,
    )

    engine = TradingEngine(exchange=client, config=risk_config)

    # ── Step 1: Fetch real market data ────────────────────────────
    print("\n[Step 1] Fetching real BTC-USDT candles...")
    try:
        candles = await client.get_candles(symbol, interval="1H", limit=100)
        print(f"  ✅ Fetched {len(candles)} candles")
        if candles:
            latest = candles[-1]
            print(f"  Latest candle: O={latest.open:.2f} H={latest.high:.2f} "
                  f"L={latest.low:.2f} C={latest.close:.2f}")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        await client.close()
        return False

    # ── Step 2: Generate signal with MomentumStrategy ────────────
    print("\n[Step 2] Generating signal with MomentumStrategy...")
    try:
        config = MomentumConfig(
            symbol=symbol,
            momentum_period=10,
            ma_short=20,
            ma_long=50,
            quantity=0.001,
        )
        strategy = MomentumStrategy(config)
        signal = await strategy.generate_signal(candles)
        print(f"  ✅ Signal: action={signal.action}, confidence={signal.confidence:.4f}")
        if signal.metadata:
            print(f"  Metadata: momentum={signal.metadata.get('momentum', 'N/A'):.4f}, "
                  f"deviation={signal.metadata.get('deviation', 'N/A'):.4f}")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        await client.close()
        return False

    # ── Step 3: Open paper position ──────────────────────────────
    print("\n[Step 3] Opening paper position...")
    try:
        # Get current price
        ticker = await client.get_ticker(symbol)
        current_price = ticker.last
        print(f"  Current price: {current_price:.2f}")

        # Determine side from signal
        side = "long" if signal.action == "buy" else "short"
        qty = config.quantity

        position = await engine.open_position(
            symbol=symbol,
            side=side,
            qty=qty,
            price=None,  # market order
        )
        print(f"  ✅ Position opened: id={position.position_id}")
        print(f" Symbol: {position.symbol}, Side: {position.side}")
        print(f"  Entry price: {position.entry_price:.2f}, Qty: {position.quantity}")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        await client.close()
        return False

    # ── Step 4: Set ATR-based stop loss ──────────────────────────
    print("\n[Step 4] Setting ATR-based stop loss...")
    try:
        new_sl = position.update_stop_loss_atr(candles, multiplier=2.0, trailing=False)
        print(f"  ✅ Stop loss set: {new_sl:.2f}")
        print(f"  ATR: {position._atr:.4f}, Stop distance: {position.get_stop_loss_distance_pct():.2f}%")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        await client.close()
        return False

    # ── Step 5: Simulate price moves and update stop loss ────────
    print("\n[Step 5] Simulating price moves and updating stop loss...")
    try:
        # Simulate a few price updates
        price_moves = [
            current_price * 1.005,   # +0.5%
            current_price * 1.010,   # +1.0%
            current_price * 1.015,   # +1.5%
        ]

        for i, new_price in enumerate(price_moves, 1):
            position.update_price(new_price)
            print(f"  Move {i}: price={new_price:.2f}, unrealized_pnl={position.unrealized_pnl:.4f}")

            # Update stop loss (trailing)
            old_sl = position.stop_loss
            new_sl = position.update_stop_loss_atr(candles, multiplier=2.0, trailing=True)
            print(f"          stop_loss: {old_sl:.2f} → {new_sl:.2f}")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        await client.close()
        return False

    # ── Step 6: Close position ───────────────────────────────────
    print("\n[Step 6] Closing position...")
    try:
        # Final price update
        final_ticker = await client.get_ticker(symbol)
        position.update_price(final_ticker.last)
        print(f"  Final price: {final_ticker.last:.2f}")
        print(f"  Unrealized PnL before close: {position.unrealized_pnl:.4f}")

        close_resp = await engine.close_position(symbol)
        print(f"  ✅ Position closed: order_id={close_resp.order_id}")
        print(f"  Filled qty: {close_resp.filled_qty}, Avg price: {close_resp.avg_price:.2f}")
        print(f"  Fee: {close_resp.fee:.4f}")
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        await client.close()
        return False

    # ── Step 7: Report PnL ───────────────────────────────────────
    print("\n[Step 7] Final Report")
    print("=" * 60)
    try:
        # Calculate realized PnL
        entry_total = position.entry_price * position.quantity
        exit_total = close_resp.avg_price * close_resp.filled_qty
        if position.side == "long":
            realized_pnl = exit_total - entry_total
        else:
            realized_pnl = entry_total - exit_total

        print(f"  Symbol:         {symbol}")
        print(f"  Side:           {position.side}")
        print(f"  Quantity:       {position.quantity}")
        print(f"  Entry price:    {position.entry_price:.2f}")
        print(f"  Exit price:     {close_resp.avg_price:.2f}")
        print(f"  Entry cost:     {entry_total:.4f} USDT")
        print(f"  Exit value:     {exit_total:.4f} USDT")
        print(f"  Realized PnL:   {realized_pnl:.4f} USDT")
        print(f"  PnL %:          {(realized_pnl / entry_total * 100):.4f}%")
        print(f"  Fee:            {close_resp.fee:.4f} USDT")
        print(f"  Net PnL:        {realized_pnl - close_resp.fee:.4f} USDT")
    except Exception as e:
        print(f"  ❌ Report failed: {type(e).__name__}: {e}")

    await client.close()

    print("\n" + "=" * 60)
    print("✅ LIVE EXECUTION LOOP TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
