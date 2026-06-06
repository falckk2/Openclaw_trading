#!/usr/bin/env python3
"""
Blofin Trading Bot — Main Entry Point

Usage:
    python run_blofin_trader.py --config config/trading.yaml

For paper trading (default), no API keys needed.
For real trading, provide API credentials in config.
"""

import asyncio
import argparse
from pathlib import Path

from src.config.config_loader import ConfigLoader
from src.exchange.blofin_client import BlofinClient
from src.paper_trading.simulator import PaperTradingEngine
from src.trading.engine import TradingEngine
from src.data.fetcher import DataFetcher
from src.data.cache import DataCache
from src.strategies.manager import StrategyManager
from src.strategies.ml.grid import GridStrategy, GridConfig
from src.strategies.ml.mean_reversion import MeanReversionStrategy, MeanReversionConfig
from src.strategies.ml.rsi_bollinger import RSIBollingerStrategy, RSIBollingerConfig
from src.executor.executor import SignalExecutor
from src.executor.risk_manager import RiskManager
from src.logging.trade_logger import TradeLogger
from src.logging.performance_logger import PerformanceLogger


async def build_trading_engine(config_path: Path):
    """Build and wire up all trading components."""
    # Load config
    config_loader = ConfigLoader.from_yaml(config_path)
    config = config_loader._config  # access raw BotConfig

    # Exchange client
    exchange = BlofinClient(
        api_key=config.exchange.api_key or "dummy",
        api_secret=config.exchange.api_secret or "dummy",
        testnet=config.exchange.testnet,
        paper_trading=config.exchange.paper_trading,
    )

    # Trading engine (real or paper)
    if config.exchange.paper_trading:
        trading_engine = PaperTradingEngine(
            exchange=exchange,
            initial_balance=config.initial_balance,
        )
    else:
        trading_engine = TradingEngine(exchange=exchange, config=config.risk)

    # Data fetcher
    cache = DataCache()
    data_fetcher = DataFetcher(exchange=exchange, cache=cache)

    # Strategies
    strategies = []
    for strat_cfg in config.strategies:
        if not strat_cfg.enabled:
            continue

        if strat_cfg.name == "grid":
            strategies.append(GridStrategy(GridConfig(
                symbol=strat_cfg.symbols[0] if strat_cfg.symbols else "BTCUSDT",
                grid_size=strat_cfg.params.get("grid_size", 5),
                price_range_pct=strat_cfg.params.get("price_range_pct", 0.05),
                order_quantity=strat_cfg.params.get("order_quantity", 0.001),
            )))
        elif strat_cfg.name == "mean_reversion":
            strategies.append(MeanReversionStrategy(MeanReversionConfig(
                symbol=strat_cfg.symbols[0] if strat_cfg.symbols else "BTCUSDT",
                window=strat_cfg.params.get("window", 20),
                std_multiplier=strat_cfg.params.get("std_multiplier", 2.0),
                quantity=strat_cfg.params.get("quantity", 0.001),
            )))
        elif strat_cfg.name == "rsi_bollinger":
            strategies.append(RSIBollingerStrategy(RSIBollingerConfig(
                symbol=strat_cfg.symbols[0] if strat_cfg.symbols else "BTCUSDT",
                rsi_period=strat_cfg.params.get("rsi_period", 14),
                rsi_oversold=strat_cfg.params.get("rsi_oversold", 30.0),
                rsi_overbought=strat_cfg.params.get("rsi_overbought", 70.0),
                quantity=strat_cfg.params.get("quantity", 0.001),
            )))

    strategy_manager = StrategyManager(strategies)

    # Executor
    risk_manager = RiskManager(config.risk)
    executor = SignalExecutor(exchange=exchange, risk_manager=risk_manager)

    # Logging
    trade_logger = TradeLogger(config.logging.trade_log_dir)
    perf_logger = PerformanceLogger(config.logging.performance_log_dir)

    return {
        "exchange": exchange,
        "trading_engine": trading_engine,
        "data_fetcher": data_fetcher,
        "strategy_manager": strategy_manager,
        "executor": executor,
        "trade_logger": trade_logger,
        "perf_logger": perf_logger,
        "config": config,
    }


async def run_trading_loop(components: dict, symbols: list[str], interval: str = "5m", check_interval: int = 60):
    """
    Main trading loop.

    Args:
        components: wired up components from build_trading_engine
        symbols: symbols to trade
        interval: candle interval
        check_interval: seconds between strategy checks
    """
    engine = components["trading_engine"]
    fetcher = components["data_fetcher"]
    strategy_mgr = components["strategy_manager"]
    executor = components["executor"]
    trade_logger = components["trade_logger"]
    config = components["config"]

    print(f"Starting trading loop for {symbols} with {interval} candles")
    print(f"Paper trading: {config.exchange.paper_trading}")

    while True:
        try:
            for symbol in symbols:
                # Get candles
                candles = await fetcher.get_candles(symbol, interval, limit=100)
                if not candles:
                    continue

                # Get current position
                position = engine.get_position(symbol)

                # Run strategies
                signals = await strategy_mgr.run_strategies(candles, symbol, position)

                for signal in signals:
                    trade_logger.log_signal(signal)

                    # Get balance for risk checks
                    if hasattr(engine, "get_balance"):
                        balance = engine.get_balance()
                        equity = balance.total_equity if hasattr(balance, "total_equity") else balance.available
                    else:
                        equity = 10000  # fallback

                    # Execute signal
                    executed, reason = await executor.execute_signal(
                        signal=signal,
                        quantity=config.strategies[0].params.get("order_quantity", 0.001),
                        positions=engine.get_all_positions(),
                        total_equity=equity,
                    )
                    print(f"[{symbol}] Signal: {signal.action} {signal.strategy_name} — {reason}")

            await asyncio.sleep(check_interval)

        except Exception as e:
            print(f"Error in trading loop: {e}")
            await asyncio.sleep(10)


async def main():
    parser = argparse.ArgumentParser(description="Blofin Trading Bot")
    parser.add_argument("--config", type=Path, default=Path("config/trading.yaml"),
                        help="Path to config file")
    args = parser.parse_args()

    print("Building trading engine...")
    components = await build_trading_engine(args.config)

    print("Starting trading loop...")
    await run_trading_loop(
        components,
        symbols=components["config"].symbols,
        interval="5m",
        check_interval=60,
    )


if __name__ == "__main__":
    asyncio.run(main())