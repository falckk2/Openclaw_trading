"""
Demo: Full paper trading flow with Blofin real API.
Run with: python3 demo_paper_trade.py
"""
import asyncio
import yaml
from src.exchange.blofin_client import BlofinClient
from src.exchange.base import OrderRequest
from src.trading.engine import TradingEngine
from src.config.dataclasses import RiskConfig
from src.paper_trading.simulator import PaperTradingSimulator


async def main():
    # Load config
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    
    # Create exchange client (paper trading mode)
    client = BlofinClient(
        api_key=config['exchange']['api_key'],
        api_secret=config['exchange']['api_secret'],
        passphrase=config['exchange']['passphrase'],
        demo=True,
        paper_trading=True,
    )
    
    # Create paper trading simulator
    simulator = PaperTradingSimulator(initial_balance=10000.0)
    
    # Create trading engine
    risk = RiskConfig(
        max_position_pct=0.1,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_daily_loss_pct=0.05,
        max_open_positions=3,
    )
    engine = TradingEngine(client, risk)
    
    print("=" * 60)
    print("PAPER TRADING DEMO")
    print("=" * 60)
    
    # Get current market price
    ticker = await client.get_ticker('BTC-USDT')
    print(f"\nBTC-USDT market price: {ticker.last}")
    
    # Place a buy order (paper trading)
    order_req = OrderRequest(
        symbol='BTC-USDT',
        side='buy',
        order_type='market',
        quantity=0.001,
        price=None,  # market order gets current price
    )
    
    print(f"\nPlacing market buy: 0.001 BTC at ~{ticker.last}")
    response = await client.place_order(order_req)
    print(f"Order filled: ID={response.order_id}, price={response.avg_price}, qty={response.filled_qty}")
    
    # Update simulator with fill
    fill = simulator.simulate_fill(
        order_id=response.order_id,
        side='buy',
        price=response.avg_price,
        quantity=response.filled_qty,
        timestamp=response.timestamp,
    )
    print(f"\nSimulator balance: {simulator.get_balance()}")
    print(f"Position: {simulator.get_position('BTC-USDT')}")
    
    # Place a sell order (take profit)
    sell_order = OrderRequest(
        symbol='BTC-USDT',
        side='sell',
        order_type='limit',
        quantity=0.001,
        price=response.avg_price * 1.02,  # 2% take profit
    )
    
    print(f"\nPlacing limit sell: 0.001 BTC at {sell_order.price} (2% take profit)")
    sell_resp = await client.place_order(sell_order)
    print(f"Order placed: ID={sell_resp.order_id}, price={sell_resp.avg_price}")
    
    # Check open orders
    open_orders = engine.order_manager.get_open_orders('BTC-USDT')
    print(f"\nOpen orders: {len(open_orders)}")
    
    print("\n" + "=" * 60)
    print("Paper trading flow complete!")
    print("=" * 60)
    
    await client.close()


if __name__ == '__main__':
    asyncio.run(main())
