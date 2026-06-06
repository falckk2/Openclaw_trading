# Blofin Trading Bot — Architecture

**Version:** 1.0  
**Date:** 2026-06-06  
**Architect:** Subagent-Architect  

---

## Design Principles

- **Single Responsibility (SRP):** Each module has one reason to change.
- **Open/Closed (OCP):** Open for extension, closed for modification.
- **Liskov Substitution (LSP):** Any exchange/strategy can replace the base.
- **Interface Segregation (ISP):** Clients depend only on what they use.
- **Dependency Inversion (DIP):** Abstractions over concretions.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MAIN ENTRY POINT                      │
│                  (run_blofin_trader.py)                     │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                      CONFIG LOADER                           │
│              (config/config_loader.py)                       │
└──────────────┬──────────────────────────────────────────────┘
               │
     ┌─────────┴───────────────────────────────────┐
     ▼                                               ▼
┌─────────────────┐                      ┌─────────────────────┐
│   EXCHANGE      │                      │      DATA           │
│   ABSTRACT      │◄─────────────────────│      FEEDER         │
│   INTERFACE     │                      │  (market data)      │
└────────┬────────┘                      └──────────┬──────────┘
         │                                        │
         ▼                                        ▼
┌─────────────────┐                   ┌─────────────────────┐
│   BLOFIN        │                   │   CACHE /           │
│   IMPLEMENTATION│                   │   HISTORICAL DB     │
└────────┬────────┘                   └─────────────────────┘
         │
         │         ┌──────────────────────────────────────┐
         └────────►│          TRADING ENGINE               │
                   │   (order mgmt, position tracking)   │
                   └──────────────┬───────────────────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              ▼                   ▼                    ▼
     ┌──────────────┐  ┌──────────────────┐  ┌─────────────┐
     │ PAPER        │  │   STRATEGY       │  │   MODELS    │
     │ TRADING      │  │   FRAMEWORK      │  │   (ML/DL)   │
     │ (simulation) │  │                  │  └──────┬──────┘
     └──────────────┘  └────────┬─────────┘         │
                                │                   │
                                ▼                   │
                   ┌────────────────────────┐       │
                   │    EXECUTOR            │◄──────┘
                   │  (signal → order)     │
                   └────────────┬───────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │     LOGGING            │
                   │  (trades, perf, issues)│
                   └────────────────────────┘
```

---

## Module Specifications

### 1. `config/` — Configuration Management

**Purpose:** Load and validate all configuration from YAML/JSON files. Single source of truth.

**Public API:**
```python
class Config:
    def load(path: Path) -> Config
    def get_exchange_config() -> ExchangeConfig
    def get_strategy_config() -> StrategyConfig
    def get_risk_config() -> RiskConfig

@dataclass
class ExchangeConfig:
    api_key: str
    api_secret: str
    testnet: bool
    paper_trading: bool

@dataclass
class StrategyConfig:
    name: str
    params: dict
    symbols: list[str]

@dataclass
class RiskConfig:
    max_position_pct: float
    stop_loss_pct: float
    max_daily_loss_pct: float
```

**SOLID:**  
- Single Responsibility: only config loading/validation  
- DIP: other modules receive Config objects, not raw dicts  

---

### 2. `exchange/` — Exchange Abstraction

**Purpose:** Abstract the exchange API behind interfaces. Allows swapping Blofin for Binance/Kraken without changing trading logic.

**Files:**
- `base.py` — abstract interface (ExchangeClient)
- `blofin_client.py` — Blofin REST + WebSocket implementation
- `exceptions.py` — exchange-specific exceptions

**Public API:**
```python
class ExchangeClient(ABC):
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker
    @abstractmethod
    async def get_order_book(self, symbol: str, depth: int) -> OrderBook
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool
    @abstractmethod
    async def get_positions(self) -> list[Position]
    @abstractmethod
    async def get_account_balance(self) -> Balance

class Ticker(NamedTuple):
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime

class OrderBook(NamedTuple):
    bids: list[tuple[float, float]]  # (price, qty)
    asks: list[tuple[float, float]]

@dataclass
class OrderRequest:
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: float
    price: float | None = None

@dataclass
class OrderResponse:
    order_id: str
    status: str
    filled_qty: float
    avg_price: float
    timestamp: datetime
```

**SOLID:**  
- ISP: thin interface with only needed methods  
- LSP: any exchange implementation replaces the base  
- OCP: add new exchanges without modifying trading engine  

---

### 3. `trading/` — Trading Engine

**Purpose:** Core order management, position tracking, P&L calculation.

**Files:**
- `engine.py` — main TradingEngine class
- `position.py` — Position dataclass
- `order_manager.py` — open orders tracking

**Public API:**
```python
class TradingEngine:
    def __init__(self, exchange: ExchangeClient, config: RiskConfig)
    async def open_position(self, symbol: str, side: str, qty: float, price: float) -> Position
    async def close_position(self, position_id: str) -> OrderResponse
    async def modify_position(self, position_id: str, stop_loss: float, take_profit: float)
    def get_positions(self) -> list[Position]
    def get_position_by_symbol(self, symbol: str) -> Position | None
    def get_unrealized_pnl(self, position_id: str) -> float
    def get_realized_pnl(self, position_id: str) -> float

@dataclass
class Position:
    position_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    quantity: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    opened_at: datetime
    stop_loss: float | None
    take_profit: float | None
```

**SOLID:**  
- SRP: only manages positions and orders, not data or strategy  
- DIP: depends on ExchangeClient abstraction, not Blofin directly  

---

### 4. `paper_trading/` — Paper Trading Engine

**Purpose:** Simulates order execution without real money. Uses real market data.

**Files:**
- `simulator.py` — PaperTradingEngine (implements same interface as TradingEngine)
- `order_tracker.py` — tracks simulated fills

**Public API:**
```python
class PaperTradingEngine:
    def __init__(self, exchange: ExchangeClient, initial_balance: float)
    async def simulate_market_buy(self, symbol: str, qty: float) -> SimulatedFill
    async def simulate_market_sell(self, symbol: str, qty: float) -> SimulatedFill
    def get_simulated_balance(self) -> SimulatedBalance
    def get_simulated_positions(self) -> list[SimulatedPosition]
    def get_trade_history(self) -> list[SimulatedTrade]

@dataclass
class SimulatedFill:
    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    fee: float
    timestamp: datetime

@dataclass
class SimulatedBalance:
    total_equity: float
    available: float
    used_margin: float
    unrealized_pnl: float
```

**SOLID:**  
- LSP: can replace TradingEngine in any context  
- OCP: add slippage/fee models without modifying real trading logic  

---

### 5. `data/` — Market Data Feeder

**Purpose:** Fetch, cache, and store market data for backtesting and live trading.

**Files:**
- `fetcher.py` — DataFetcher (uses exchange abstraction)
- `cache.py` — in-memory + file cache for candles
- `storage.py` — historical candle storage (SQLite or CSV)

**Public API:**
```python
class DataFetcher:
    def __init__(self, exchange: ExchangeClient, cache: DataCache)
    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]
    async def get_ticker(self, symbol: str) -> Ticker
    async def stream_candles(self, symbol: str, interval: str) -> AsyncGenerator[Candle, None]

@dataclass
class Candle(NamedTuple):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class DataCache:
    def get(self, key: str) -> Any | None
    def set(self, key: str, value: Any, ttl: int = 300)
    def clear_expired()
```

**SOLID:**  
- SRP: only data fetching and caching  
- DIP: uses ExchangeClient abstraction  

---

### 6. `strategies/` — Strategy Framework

**Purpose:** Pluggable strategy system. Strategies signal when to buy/sell.

**Files:**
- `base.py` — Strategy abstract base class
- `signal.py` — Signal dataclass
- `manager.py` — StrategyManager (runs strategies on data)
- `ml/` — ML strategy implementations

**Public API:**
```python
class Strategy(ABC):
    @property
    def name(self) -> str
    @property
    def required_features(self) -> list[str]
    @abstractmethod
    async def generate_signal(self, candles: list[Candle], position: Position | None) -> Signal | None
    @abstractmethod
    async def on_candle(self, candle: Candle) -> Signal | None
    def validate(self) -> bool: ...

@dataclass
class Signal:
    signal_id: str
    strategy_name: str
    symbol: str
    action: Literal["buy", "sell", "hold"]
    confidence: float  # 0.0-1.0
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    metadata: dict
    timestamp: datetime

class StrategyManager:
    def __init__(self, strategies: list[Strategy])
    async def run_strategies(self, candles: list[Candle], positions: list[Position]) -> list[Signal]
    def add_strategy(self, strategy: Strategy)
    def remove_strategy(self, name: str)
```

**SOLID:**  
- OCP: add new strategies without modifying framework  
- LSP: any Strategy subclass can replace another  
- ISP: Strategy only has what a strategy needs  

---

### 7. `strategies/ml/` — ML Strategies

**Files:**
- `grid.py` — Grid Trading Strategy
- `mean_reversion.py` — Mean Reversion Strategy
- `rsi_bollinger.py` — RSI + Bollinger Bands Strategy

**Each strategy:**
```python
class GridStrategy(Strategy):
    def __init__(self, config: GridConfig)
    async def generate_signal(...) -> Signal | None

@dataclass
class GridConfig:
    symbol: str
    grid_size: int
    price_range_pct: float
    order_quantity: float
```

---

### 8. `models/` — ML/DL Model Management

**Purpose:** Train, store, and serve ML models for strategy signals.

**Files:**
- `base.py` — ModelBase abstract class
- `trainer.py` — ModelTrainer (offline training)
- `inference.py` — ModelInference (real-time predictions)
- `registry.py` — ModelRegistry (versioning, loading)
- `features/` — feature engineering utilities

**Public API:**
```python
class ModelBase(ABC):
    @property
    def name(self) -> str
    @property
    def version(self) -> str
    @abstractmethod
    def predict(self, features: np.ndarray) -> np.ndarray
    @abstractmethod
    async def train(self, X: np.ndarray, y: np.ndarray) -> TrainingResult

class ModelRegistry:
    def register(self, model: ModelBase)
    def load(self, name: str, version: str) -> ModelBase
    def list_models(self) -> list[ModelInfo]

class ModelInference:
    def __init__(self, model: ModelBase, feature_pipeline: FeaturePipeline)
    async def predict(self, candles: list[Candle]) -> Signal
```

**SOLID:**  
- SRP: model training vs inference vs registry are separate concerns  
- OCP: add new model types without modifying inference  

---

### 9. `logging/` — Trade & Performance Logging

**Purpose:** Log all trades, signals, P&L, and issues to files for analysis.

**Files:**
- `trade_logger.py` — logs every trade with full detail
- `performance_logger.py` — logs daily/weekly performance
- `issue_logger.py` — logs issues to issues.md
- `formatters.py` — structured log formatting

**Public API:**
```python
class TradeLogger:
    def log_signal(self, signal: Signal)
    def log_order(self, order: OrderResponse)
    def log_trade(self, trade: Trade)
    def log_pnl(self, realized: float, unrealized: float)

class IssueLogger:
    def log_issue(self, issue: Issue)
    def get_open_issues(self) -> list[Issue]
    def resolve_issue(self, issue_id: str, resolution: str)

class PerformanceLogger:
    def log_daily_summary(self, summary: DailySummary)
    def log_trade_summary(self, trades: list[Trade])
```

---

### 10. `executor/` — Signal → Order Executor

**Purpose:** Converts strategy signals into actual orders, respecting risk limits.

**Files:**
- `executor.py` — SignalExecutor
- `risk_manager.py` — checks risk limits before placing orders

**Public API:**
```python
class SignalExecutor:
    def __init__(self, trading_engine: TradingEngine | PaperTradingEngine, risk_manager: RiskManager)
    async def execute(self, signal: Signal) -> OrderResponse | None
    # returns None if risk check fails

class RiskManager:
    def check_position_limits(self, symbol: str, qty: float) -> bool
    def check_daily_loss(self) -> bool
    def check_max_position_size(self, symbol: str, qty: float, price: float) -> bool
```

---

## Directory Structure

```
blofin_trader/
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config_loader.py
│   │   └── dataclasses.py
│   ├── exchange/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── blofin_client.py
│   │   └── exceptions.py
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── position.py
│   │   └── order_manager.py
│   ├── paper_trading/
│   │   ├── __init__.py
│   │   ├── simulator.py
│   │   └── order_tracker.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetcher.py
│   │   ├── cache.py
│   │   └── storage.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── signal.py
│   │   ├── manager.py
│   │   └── ml/
│   │       ├── __init__.py
│   │       ├── grid.py
│   │       ├── mean_reversion.py
│   │       └── rsi_bollinger.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── trainer.py
│   │   ├── inference.py
│   │   ├── registry.py
│   │   └── features/
│   │       ├── __init__.py
│   │       └── feature_builder.py
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── trade_logger.py
│   │   ├── performance_logger.py
│   │   ├── issue_logger.py
│   │   └── formatters.py
│   └── executor/
│       ├── __init__.py
│       ├── executor.py
│       └── risk_manager.py
├── tests/
│   ├── __init__.py
│   ├── test_exchange.py
│   ├── test_trading.py
│   ├── test_strategies.py
│   └── test_models.py
├── logs/
│   ├── trades/
│   ├── performance/
│   └── issues/
├── config/
│   ├── base_config.yaml
│   ├── strategies/
│   └── secrets.yaml (gitignored)
├── docs/
│   └── ARCHITECTURE.md
├── requirements.txt
├── run_blofin_trader.py
└── README.md
```

---

## Execution Flow

### Paper Trading Run
1. `run_blofin_trader.py` loads config
2. Config creates BlofinExchangeClient (paper mode)
3. DataFetcher starts streaming candles
4. StrategyManager receives candles, generates Signals
5. SignalExecutor receives Signals, checks risk
6. PaperTradingEngine executes simulated orders
7. TradeLogger records everything
8. PerformanceLogger summarizes

### Real Trading Run
Same flow, replace PaperTradingEngine with TradingEngine.

---

## SOLID Compliance Checklist

| Module | SRP | OCP | LSP | ISP | DIP |
|--------|-----|-----|-----|-----|-----|
| config | ✅ | ✅ | ✅ | ✅ | ✅ |
| exchange | ✅ | ✅ | ✅ | ✅ | ✅ |
| trading | ✅ | ✅ | ✅ | ✅ | ✅ |
| paper_trading | ✅ | ✅ | ✅ | ✅ | ✅ |
| data | ✅ | ✅ | ✅ | ✅ | ✅ |
| strategies | ✅ | ✅ | ✅ | ✅ | ✅ |
| models | ✅ | ✅ | ✅ | ✅ | ✅ |
| logging | ✅ | ✅ | ✅ | ✅ | ✅ |
| executor | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Next Steps (for Engineer agent)
1. Implement `config/config_loader.py` and `config/dataclasses.py`
2. Implement `exchange/base.py` and `exchange/blofin_client.py`
3. Implement `paper_trading/simulator.py`
4. Implement `trading/engine.py`
5. Implement `data/fetcher.py` and `data/cache.py`
6. Wire up `run_blofin_trader.py` with all modules