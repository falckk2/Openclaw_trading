# Blofin Trading Bot

ML-powered crypto trading bot for Blofin exchange, with paper trading first.

## Architecture

See `docs/ARCHITECTURE.md` for full architecture details.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run paper trading (no API keys needed)
python run_blofin_trader.py --config config/trading.yaml
```

## Project Structure

```
src/
├── config/       # Configuration loading (YAML)
├── exchange/     # Exchange abstraction + Blofin client
├── trading/      # Trading engine, position management
├── paper_trading/# Simulated order execution
├── data/         # Market data fetching and caching
├── strategies/   # Strategy framework + ML implementations
│   └── ml/       # Grid, Mean Reversion, RSI+Bollinger
├── models/       # ML/DL model management
├── logging/      # Trade logs, performance logs, issue tracking
└── executor/    # Signal → Order execution with risk management

tests/            # Pytest tests for each module
logs/             # Trade and performance logs
config/           # YAML config files
docs/             # Architecture documentation
```

## Modules

| Module | Purpose |
|--------|---------|
| `exchange` | Abstract interface + Blofin REST client |
| `trading` | Position management, P&L, order management |
| `paper_trading` | Simulated execution (LSP-substitutable for trading) |
| `strategies` | Strategy framework + 3 ML strategies |
| `models` | Feature engineering + model training/inference |
| `logging` | Trade logging, performance tracking, issues.md |
| `executor` | Risk-checked signal execution |

## Strategies

- **Grid** — buy low/sell high in price bands
- **Mean Reversion** — buy below moving average, sell above
- **RSI + Bollinger** — overbought/oversold with volatility channels

## Design Principles

All code follows SOLID principles:
- **S**ingle Responsibility — each module has one reason to change
- **O**pen/Closed — open for extension, closed for modification
- **L**iskov Substitution — paper_trading can replace trading transparently
- **I**nterface Segregation — thin interfaces, no fat dependencies
- **D**ependency Inversion — depend on abstractions, not concretions

## Agents

| Agent | Specialty |
|-------|-----------|
| Architect | Code structure, SOLID compliance |
| Engineer | Implementation |
| BugFinder | Logging, issue discovery |
| Debugger | Issue resolution |
| Tester | Validation, tests |

All agents write to `issues.md` in standardized format.

## Token Budget

This project is built with a token budget constraint — the Architect agent stops at 90% usage.
See `token_budget.json` for current tracking.