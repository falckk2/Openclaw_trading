"""Configuration loader — loads and validates YAML/JSON config files."""

from pathlib import Path
from typing import Any

import yaml

from .dataclasses import (
    BotConfig,
    DataConfig,
    ExchangeConfig,
    LoggingConfig,
    RiskConfig,
    StrategyConfig,
)


class ConfigLoader:
    """Loads configuration from YAML files and constructs BotConfig."""

    @staticmethod
    def load_yaml(path: Path) -> dict[str, Any]:
        """Load a YAML file and return a dict."""
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path) as f:
            return yaml.safe_load(f) or {}

    @classmethod
    def from_yaml(cls, config_path: Path) -> BotConfig:
        """Load BotConfig from a YAML file."""
        data = cls.load_yaml(config_path)
        return cls._build_config(data)

    @classmethod
    def _build_config(cls, data: dict) -> BotConfig:
        """Build BotConfig from a dict."""
        exchange_data = data.get("exchange", {})
        exchange = ExchangeConfig(
            api_key=exchange_data.get("api_key", ""),
            api_secret=exchange_data.get("api_secret", ""),
            testnet=exchange_data.get("testnet", True),
            paper_trading=exchange_data.get("paper_trading", True),
            rest_endpoint=exchange_data.get("rest_endpoint", ""),
            ws_endpoint=exchange_data.get("ws_endpoint", ""),
        )

        risk_data = data.get("risk", {})
        risk = RiskConfig(
            max_position_pct=risk_data.get("max_position_pct", 0.1),
            stop_loss_pct=risk_data.get("stop_loss_pct", 0.02),
            take_profit_pct=risk_data.get("take_profit_pct", 0.04),
            max_daily_loss_pct=risk_data.get("max_daily_loss_pct", 0.05),
            max_open_positions=risk_data.get("max_open_positions", 3),
        )

        strategies = [
            StrategyConfig(name=s.get("name", "unknown"), enabled=s.get("enabled", True),
                           params=s.get("params", {}), symbols=s.get("symbols", []))
            for s in data.get("strategies", [])
        ]

        data_cfg = DataConfig(**data.get("data", {}))
        logging_cfg = LoggingConfig(**data.get("logging", {}))

        return BotConfig(
            exchange=exchange,
            risk=risk,
            strategies=strategies,
            data=data_cfg,
            logging=logging_cfg,
            initial_balance=data.get("initial_balance", 10000.0),
            symbols=data.get("symbols", ["BTCUSDT"]),
        )

    def get_exchange_config(self) -> ExchangeConfig:
        """Get exchange config (for compatibility)."""
        return self._config.exchange

    def get_strategy_config(self) -> list[StrategyConfig]:
        """Get strategy configs."""
        return self._config.strategies

    def get_risk_config(self) -> RiskConfig:
        """Get risk config."""
        return self._config.risk