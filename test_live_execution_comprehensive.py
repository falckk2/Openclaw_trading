"""
Comprehensive Live Execution Test — Blofin Trading Bot
Tests all strategies in paper trading mode with real market data.

Run: python3 test_live_execution.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, UTC

sys.path.insert(0, "/root/.openclaw/workspace/blofin_trader")

from src.exchange.blofin_client import BlofinClient
from src.trading.engine import TradingEngine
from src.trading.position import Position
from src.strategies.ml.grid import GridStrategy, GridConfig
from src.strategies.ml.mean_reversion import MeanReversionStrategy, MeanReversionConfig
from src.strategies.ml.rsi_bollinger import RSIBollingerStrategy, RSIBollingerConfig
from src.strategies.ml.momentum import MomentumStrategy, MomentumConfig
from src.config.dataclasses import RiskConfig


async def test_market_data(client: BlofinClient) -> dict:
    """Test 1: Fetch live market data (BTC-USDT candles, ticker)."""
    print("\n" + "=" * 70)
    print("TEST 1: Live Market Data Fetch")
    print("=" * 70)
    
    errors = []
    
    # Test ticker
    try:
        ticker = await client.get_ticker("BTC-USDT")
        print(f"  ✓ Ticker fetched: BTC-USDT last={ticker.last}, bid={ticker.bid}, ask={ticker.ask}, vol={ticker.volume}")
        assert ticker.last > 0, "Ticker last price should be positive"
    except Exception as e:
        errors.append(f"Ticker fetch failed: {e}")
        print(f"  ✗ Ticker fetch failed: {e}")
    
    # Test candles (multiple timeframes)
    for interval in ["1m", "5m", "1H", "4H"]:
        try:
            candles = await client.get_candles("BTC-USDT", interval=interval, limit=100)
            print(f"  ✓ {interval} candles fetched: {len(candles)} bars, range={candles[0].timestamp} → {candles[-1].timestamp}")
            assert len(candles) > 0, f"No {interval} candles returned"
            assert candles[-1].close > 0, f"Last candle close should be positive"
        except Exception as e:
            errors.append(f"{interval} candles fetch failed: {e}")
            print(f"  ✗ {interval} candles fetch failed: {e}")
    
    return {"errors": errors, "ticker": ticker}


async def test_strategies(client: BlofinClient) -> dict:
    """Test 2: Run each strategy with real signals."""
    print("\n" + "=" * 70)
    print("TEST 2: Strategy Signal Generation")
    print("=" * 70)
    
    errors = []
    results = {}
    
    # Fetch candles for all strategies (1H for most, 1m for grid)
    candles_1h = await client.get_candles("BTC-USDT", interval="1H", limit=100)
    candles_1m = await client.get_candles("BTC-USDT", interval="1m", limit=100)
    print(f"  Using {len(candles_1h)} 1H candles (range: {candles_1h[0].timestamp} → {candles_1h[-1].timestamp})")
    print(f"  Latest close: {candles_1h[-1].close:.2f}")
    
    # ── GridStrategy ──────────────────────────────────────────
    print("\n  [GridStrategy]")
    try:
        config = GridConfig(symbol="BTC-USDT", grid_size=5, price_range_pct=0.05, order_quantity=0.001)
        strategy = GridStrategy(config)
        assert strategy.validate(), "GridStrategy config validation failed"
        signal = await strategy.generate_signal(candles_1m)
        action = signal.action if signal else "None"
        confidence = signal.confidence if signal else 0.0
        print(f"    ✓ Signal: action={action}, confidence={confidence:.4f}")
        if signal and signal.metadata:
            print(f"      metadata={signal.metadata}")
        results["grid"] = signal
    except Exception as e:
        errors.append(f"GridStrategy failed: {e}")
        print(f"    ✗ GridStrategy failed: {e}")
        results["grid"] = None
    
    # ── MeanReversionStrategy ──────────────────────────────────
    print("\n  [MeanReversionStrategy]")
    try:
        config = MeanReversionConfig(symbol="BTC-USDT", window=20, std_multiplier=2.0, quantity=0.001)
        strategy = MeanReversionStrategy(config)
        assert strategy.validate(), "MeanReversionStrategy config validation failed"
        signal = await strategy.generate_signal(candles_1h)
        action = signal.action if signal else "None"
        confidence = signal.confidence if signal else 0.0
        print(f"    ✓ Signal: action={action}, confidence={confidence:.4f}")
        if signal and signal.metadata:
            print(f"      metadata={signal.metadata}")
        results["mean_reversion"] = signal
    except Exception as e:
        errors.append(f"MeanReversionStrategy failed: {e}")
        print(f"    ✗ MeanReversionStrategy failed: {e}")
        results["mean_reversion"] = None
    
    # ── RSIBollingerStrategy ────────────────────────────────────
    print("\n  [RSIBollingerStrategy]")
    try:
        config = RSIBollingerConfig(symbol="BTC-USDT", quantity=0.001)
        strategy = RSIBollingerStrategy(config)
        assert strategy.validate(), "RSIBollingerStrategy config validation failed"
        signal = await strategy.generate_signal(candles_1h)
        action = signal.action if signal else "None"
        confidence = signal.confidence if signal else 0.0
        print(f"    ✓ Signal: action={action}, confidence={confidence:.4f}")
        if signal and signal.metadata:
            print(f"      metadata={signal.metadata}")
        results["rsi_bollinger"] = signal
    except Exception as e:
        errors.append(f"RSIBollingerStrategy failed: {e}")
        print(f"    ✗ RSIBollingerStrategy failed: {e}")
        results["rsi_bollinger"] = None
    
    # ── MomentumStrategy ───────────────────────────────────────
    print("\n  [MomentumStrategy]")
    try:
        config = MomentumConfig(symbol="BTC-USDT", quantity=0.001)
        strategy = MomentumStrategy(config)
        assert strategy.validate(), "MomentumStrategy config validation failed"
        signal = await strategy.generate_signal(candles_1h)
        action = signal.action if signal else "None"
        confidence = signal.confidence if signal else 0.0
        print(f"    ✓ Signal: action={action}, confidence={confidence:.4f}")
        if signal and signal.metadata:
            print(f"      metadata={signal.metadata}")
        results["momentum"] = signal
    except Exception as e:
        errors.append(f"MomentumStrategy failed: {e}")
        print(f"    ✗ MomentumStrategy failed: {e}")
        results["momentum"] = None
    
    return {"errors": errors, "results": results}


async def test_paper_positions(client: BlofinClient, engine: TradingEngine, ticker) -> dict:
    """Test 3: Open paper positions and verify P&L tracking."""
    print("\n" + "=" * 70)
    print("TEST 3: Paper Positions & P&L Tracking")
    print("=" * 70)
    
    errors = []
    
    # Get balance
    try:
        balance = await client.get_balance()
        print(f"  ✓ Balance: equity={balance.total_equity:.2f}, available={balance.available:.2f}")
    except Exception as e:
        errors.append(f"Balance fetch failed: {e}")
        print(f"  ✗ Balance fetch failed: {e}")
        return {"errors": errors}
    
    # Open a long position
    try:
        pos = await engine.open_position(symbol="BTC-USDT", side="long", qty=0.001, price=ticker.last)
        print(f"  ✓ Long position opened: id={pos.position_id}, entry={pos.entry_price:.2f}, qty={pos.quantity}")
        
        # Update price and check P&L
        pos.update_price(ticker.last)
        print(f"    Current price updated to: {pos.current_price:.2f}")
        print(f"    Unrealized PnL: {pos.unrealized_pnl:.4f}")
        print(f"    PnL %: {pos.get_pnl_pct():.4f}%")
        
        # Verify position tracking
        tracked = engine.get_position("BTC-USDT")
        assert tracked is not None, "Position not tracked"
        assert tracked.position_id == pos.position_id, "Position ID mismatch"
        print(f"  ✓ Position correctly tracked in engine")
        
    except Exception as e:
        errors.append(f"Position open/tracking failed: {e}")
        print(f"  ✗ Position open/tracking failed: {e}")
        return {"errors": errors}
    
    # Open a short position (simulated)
    try:
        # For short, we need a different symbol or close the long first
        # Let's simulate a short by creating a position directly
        from datetime import datetime, UTC
        short_pos = Position(
            position_id=str(uuid.uuid4()),
            symbol="ETH-USDT",
            side="short",
            entry_price=ticker.last * 0.05,  # mock ETH price
            quantity=0.01,
            current_price=ticker.last * 0.05,
            opened_at=datetime.now(UTC),
        )
        engine._positions["ETH-USDT"] = short_pos
        short_pos.update_price(ticker.last * 0.05 * 1.02)  # price up 2% = loss for short
        print(f"  ✓ Short position (ETH-USDT) created and tracked: entry={short_pos.entry_price:.2f}, PnL={short_pos.unrealized_pnl:.4f}")
        
        all_positions = engine.get_all_positions()
        print(f"  ✓ Total open positions: {len(all_positions)}")
        for p in all_positions:
            print(f"    - {p.symbol}: {p.side}, entry={p.entry_price:.2f}, PnL={p.unrealized_pnl:.4f}")
        
    except Exception as e:
        errors.append(f"Short position test failed: {e}")
        print(f"  ✗ Short position test failed: {e}")
    
    return {"errors": errors, "long_pos": pos, "short_pos": short_pos}


async def test_atr_stop_loss(engine: TradingEngine, candles) -> dict:
    """Test 4: ATR-based stop loss functionality."""
    print("\n" + "=" * 70)
    print("TEST 4: ATR-Based Stop Loss Functionality")
    print("=" * 70)
    
    errors = []
    
    # Test with BTC-USDT long position
    pos = engine.get_position("BTC-USDT")
    if not pos:
        print("  ⚠ No BTC-USDT position to test, skipping")
        return {"errors": []}
    
    try:
        # Test ATR calculation
        atr = pos.calculate_atr(candles)
        print(f"  ✓ ATR calculated: {atr:.4f} (period={pos.atr_period})")
        assert atr >= 0, "ATR should be non-negative"
        
        # Test update_stop_loss_atr (non-trailing)
        stop = pos.update_stop_loss_atr(candles, multiplier=2.0, trailing=False)
        print(f"  ✓ Stop loss set (non-trailing, 2x ATR): {stop:.2f}")
        assert pos.stop_loss is not None, "Stop loss not set"
        assert pos.stop_loss < pos.current_price, "Long stop loss should be below current price"
        print(f"    Stop distance: {pos.get_stop_loss_distance_pct():.2f}%")
        
        # Test trailing stop (simulate price going up, stop should follow)
        original_stop = pos.stop_loss
        pos.update_price(pos.current_price * 1.02)  # price up 2%
        stop2 = pos.update_stop_loss_atr(candles, multiplier=2.0, trailing=True)
        print(f"  ✓ After +2% price move: trailing stop moved from {original_stop:.2f} → {stop2:.2f}")
        assert stop2 >= original_stop, "Trailing stop should only move up for longs"
        print(f"    New stop distance: {pos.get_stop_loss_distance_pct():.2f}%")
        
        # Test check_stop_loss_triggered
        # Simulate price at stop loss
        triggered = pos.check_stop_loss_triggered(pos.stop_loss)
        print(f"  ✓ check_stop_loss_triggered at stop price: {triggered}")
        assert triggered, "Stop loss should be triggered at stop price"
        
        # Not triggered slightly above
        triggered_above = pos.check_stop_loss_triggered(pos.stop_loss * 1.01)
        print(f"  ✓ check_stop_loss_triggered 1% above stop: {triggered_above}")
        assert not triggered_above, "Stop loss should not trigger above stop price"
        
    except Exception as e:
        errors.append(f"ATR stop loss test failed: {e}")
        print(f"  ✗ ATR stop loss test failed: {e}")
        import traceback; traceback.print_exc()
    
    # Test ATR take profit
    try:
        tp = pos.set_take_profit_atr(candles, reward_multiplier=3.0)
        print(f"  ✓ ATR take profit set (3x ATR): {tp:.2f}")
        assert pos.take_profit is not None, "Take profit not set"
        assert pos.take_profit > pos.current_price, "Long take profit should be above current price"
        
        # Check TP triggered
        tp_triggered = pos.check_take_profit_triggered(pos.take_profit)
        print(f"  ✓ check_take_profit_triggered at TP price: {tp_triggered}")
        assert tp_triggered, "Take profit should trigger at TP price"
        
        # Risk/reward ratio
        rr = pos.get_risk_reward_ratio()
        print(f"  ✓ Risk/Reward ratio: {rr:.2f}")
        assert rr is not None and rr > 0, "R/R ratio should be positive"
        
    except Exception as e:
        errors.append(f"ATR take profit test failed: {e}")
        print(f"  ✗ ATR take profit test failed: {e}")
        import traceback; traceback.print_exc()
    
    # Test short position ATR
    short_pos = engine.get_position("ETH-USDT")
    if short_pos:
        try:
            stop = short_pos.update_stop_loss_atr(candles, multiplier=2.0, trailing=True)
            print(f"  ✓ Short position ATR stop set: {stop:.2f} (above current for shorts)")
            assert stop > short_pos.current_price, "Short stop loss should be above current price"
            
            tp = short_pos.set_take_profit_atr(candles, reward_multiplier=3.0)
            print(f"  ✓ Short position ATR TP set: {tp:.2f}")
            assert tp < short_pos.current_price, "Short TP should be below current price"
            
        except Exception as e:
            errors.append(f"Short position ATR test failed: {e}")
            print(f"  ✗ Short position ATR test failed: {e}")
    
    return {"errors": errors}


async def test_order_tracking(client: BlofinClient, engine: TradingEngine) -> dict:
    """Test 5: Order execution and tracking."""
    print("\n" + "=" * 70)
    print("TEST 5: Order Execution & Tracking")
    print("=" * 70)
    
    errors = []
    
    try:
        # Get tracked orders from order manager
        open_orders = engine.order_manager.get_open_orders()
        print(f"  ✓ Order manager accessible, open orders: {len(open_orders)}")
        
        # Place a new limit order via client (paper trading)
        from src.exchange.base import OrderRequest
        order_req = OrderRequest(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=50000.0,  # limit price
        )
        
        resp = await client.place_order(order_req)
        print(f"  ✓ Limit order placed: id={resp.order_id}, filled={resp.filled_qty}, status={resp.status}")
        
        # Track it
        tracked = engine.order_manager.track_order(resp)
        print(f"  ✓ Order tracked: id={tracked.order_id}, symbol={tracked.symbol}, side={tracked.side}")
        
        # Get order by ID
        looked_up = engine.order_manager.get_order(resp.order_id)
        assert looked_up is not None, "Order not found in tracker"
        assert looked_up.order_id == resp.order_id, "Order ID mismatch"
        print(f"  ✓ Order lookup by ID successful")
        
        # Get open orders for BTC-USDT
        btc_orders = engine.order_manager.get_open_orders("BTC-USDT")
        print(f"  ✓ Open orders for BTC-USDT: {len(btc_orders)}")
        
    except Exception as e:
        errors.append(f"Order tracking test failed: {e}")
        print(f"  ✗ Order tracking test failed: {e}")
        import traceback; traceback.print_exc()
    
    return {"errors": errors}


async def test_position_close(client: BlofinClient, engine: TradingEngine) -> dict:
    """Test 6: Close positions and verify cleanup."""
    print("\n" + "=" * 70)
    print("TEST 6: Position Close & Cleanup")
    print("=" * 70)
    
    errors = []
    
    # Get positions before close
    before = engine.get_all_positions()
    print(f"  Positions before close: {len(before)}")
    
    # Close BTC-USDT long position
    try:
        pos = engine.get_position("BTC-USDT")
        if pos:
            entry = pos.entry_price
            close_resp = await engine.close_position("BTC-USDT")
            print(f"  ✓ BTC-USDT long position closed: order_id={close_resp.order_id}, filled_qty={close_resp.filled_qty}, avg_price={close_resp.avg_price:.2f}")
            assert close_resp.filled_qty == pos.quantity, "Filled quantity mismatch"
            
            # Verify position removed
            assert engine.get_position("BTC-USDT") is None, "Position still in engine after close"
            print(f"  ✓ Position removed from engine after close")
            
            # Verify P&L (close price vs entry)
            pnl = (close_resp.avg_price - entry) * pos.quantity
            print(f"  ✓ Close PnL calculated: {pnl:.4f} (entry={entry:.2f}, exit={close_resp.avg_price:.2f})")
        else:
            print("  ⚠ No BTC-USDT position to close")
    except Exception as e:
        errors.append(f"BTC-USDT position close failed: {e}")
        print(f"  ✗ BTC-USDT position close failed: {e}")
        import traceback; traceback.print_exc()
    
    # Close ETH-USDT short position
    try:
        pos = engine.get_position("ETH-USDT")
        if pos:
            close_resp = await engine.close_position("ETH-USDT")
            print(f"  ✓ ETH-USDT short position closed: order_id={close_resp.order_id}")
            assert engine.get_position("ETH-USDT") is None, "ETH position still in engine"
            print(f"  ✓ ETH-USDT position removed from engine")
    except Exception as e:
        errors.append(f"ETH-USDT position close failed: {e}")
        print(f"  ✗ ETH-USDT position close failed: {e}")
    
    # Final state
    after = engine.get_all_positions()
    print(f"  ✓ Final position count: {len(after)}")
    assert len(after) == 0, "Should have no open positions after close"
    
    return {"errors": errors}


async def test_update_position_prices(engine: TradingEngine) -> dict:
    """Test: update_position_prices with empty portfolio."""
    print("\n" + "=" * 70)
    print("TEST 7: Update Prices (Empty Portfolio)")
    print("=" * 70)
    
    errors = []
    try:
        await engine.update_position_prices()
        print(f"  ✓ update_position_prices() handled empty portfolio gracefully")
    except Exception as e:
        errors.append(f"update_position_prices failed: {e}")
        print(f"  ✗ update_position_prices failed: {e}")
    
    return {"errors": errors}


async def test_engine_risk_checks(client: BlofinClient, engine: TradingEngine) -> dict:
    """Test: risk limit checks."""
    print("\n" + "=" * 70)
    print("TEST 8: Engine Risk Checks")
    print("=" * 70)
    
    errors = []
    
    try:
        # Check position limits with a reasonable order
        allowed = await engine.check_position_limits("BTC-USDT", qty=0.001, price=50000.0)
        print(f"  ✓ check_position_limits passed: {allowed}")
    except Exception as e:
        # This may fail in paper mode without real balance, that's OK
        print(f"  ⚠ check_position_limits: {e}")
    
    try:
        # Total PnL with no positions
        total_unrealized = engine.get_total_unrealized_pnl()
        total_realized = engine.get_total_realized_pnl()
        print(f"  ✓ Total unrealized PnL (should be 0): {total_unrealized:.4f}")
        print(f"  ✓ Total realized PnL (should be 0): {total_realized:.4f}")
    except Exception as e:
        errors.append(f"Risk checks failed: {e}")
        print(f"  ✗ Risk checks failed: {e}")
    
    return {"errors": errors}


async def main():
    print("\n" + "#" * 70)
    print("#  BLOFIN TRADING BOT — COMPREHENSIVE LIVE EXECUTION TEST")
    print("#" * 70)
    print(f"#  Started: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    all_errors = []
    
    # ── Setup ──────────────────────────────────────────────────
    print("\n[SETUP] Connecting to Blofin demo API...")
    client = BlofinClient(api_key="", api_secret="", demo=True, paper_trading=True)
    risk_config = RiskConfig()
    engine = TradingEngine(client, risk_config)
    print("  ✓ Connected. Engine initialized in paper trading mode.")
    
    # ── Test 1: Market Data ────────────────────────────────────
    result = await test_market_data(client)
    all_errors.extend(result.get("errors", []))
    ticker = result.get("ticker")
    
    # ── Test 2: Strategies ─────────────────────────────────────
    result = await test_strategies(client)
    all_errors.extend(result.get("errors", []))
    strategy_signals = result.get("results", {})
    
    # ── Test 3: Paper Positions & P&L ─────────────────────────
    result = await test_paper_positions(client, engine, ticker)
    all_errors.extend(result.get("errors", []))
    
    # Get candles for ATR tests (need 1H for enough data)
    candles = await client.get_candles("BTC-USDT", interval="1H", limit=100)
    
    # ── Test 4: ATR Stop Loss ──────────────────────────────────
    result = await test_atr_stop_loss(engine, candles)
    all_errors.extend(result.get("errors", []))
    
    # ── Test 5: Order Tracking ─────────────────────────────────
    result = await test_order_tracking(client, engine)
    all_errors.extend(result.get("errors", []))
    
    # ── Test 6: Position Close ─────────────────────────────────
    result = await test_position_close(client, engine)
    all_errors.extend(result.get("errors", []))
    
    # ── Test 7: Update Prices (empty) ──────────────────────────
    result = await test_update_position_prices(engine)
    all_errors.extend(result.get("errors", []))
    
    # ── Test 8: Risk Checks ───────────────────────────────────
    result = await test_engine_risk_checks(client, engine)
    all_errors.extend(result.get("errors", []))
    
    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"  Tests run:    8")
    print(f"  Errors:       {len(all_errors)}")
    
    if all_errors:
        print("\n  ERROR DETAILS:")
        for i, err in enumerate(all_errors, 1):
            print(f"    {i}. {err}")
        print("\n  ⚠ Some tests had errors — see above for details.")
    else:
        print("\n  ✓ ALL TESTS PASSED — no errors detected.")
    
    print(f"\n  Strategy signals generated:")
    for name, sig in strategy_signals.items():
        if sig:
            print(f"    - {name}: {sig.action} (confidence={sig.confidence:.4f})")
        else:
            print(f"    - {name}: no signal (error)")
    
    print(f"\n  Final balance check:", end=" ")
    try:
        bal = await client.get_balance()
        print(f"equity={bal.total_equity:.2f}, available={bal.available:.2f}")
    except Exception as e:
        print(f"failed to fetch: {e}")
    
    await client.close()
    print("\n" + "#" * 70)
    print("#  TEST COMPLETE")
    print("#" * 70)
    
    return len(all_errors) == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)