"""Configuration dataclasses for the trading bot."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class ExchangeConfig:
    """Exchange connection configuration."""
    api_key: str
    api_secret: str
    testnet: bool = True
    paper_trading: bool = True
    rest_endpoint: str = ""
    ws_endpoint: str = ""

    def __post_init__(self):
        if not self.api_key or not self.api_secret:
            raise ValueError("api_key and api_secret are required")


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_pct: float = 0.1  # max 10% of equity per position
    stop_loss_pct: float = 0.02    # 2% stop loss
    take_profit_pct: float = 0.04 # 4% take profit
    max_daily_loss_pct: float = 0.05  # 5% max daily loss
    max_open_positions: int = 3


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    name: str
    enabled: bool = True
    params: dict = field(default_factory=dict)
    symbols: list[str] = field(default_factory=list)


@dataclass
class DataConfig:
    """Market data configuration."""
    candles_cache_ttl: int = 300  # seconds
    candle_intervals: list[str] = field(default_factory=lambda: ["1m", "5m", "1h"])
    max_candles_per_fetch: int = 1000


@dataclass
class LoggingConfig:
    """Logging configuration."""
    trade_log_dir: Path = field(default_factory=lambda: Path("logs/trades"))
    performance_log_dir: Path = field(default_factory=lambda: Path("logs/performance"))
    issue_log_dir: Path = field(default_factory=lambda: Path("logs/issues"))
    log_level: str = "INFO"


@dataclass
class BotConfig:
    """Root configuration object."""
    exchange: ExchangeConfig
    risk: RiskConfig
    strategies: list[StrategyConfig] = field(default_factory=list)
    data: DataConfig = field(default_factory=DataConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    initial_balance: float = 10000.0  # paper trading starting balance
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])