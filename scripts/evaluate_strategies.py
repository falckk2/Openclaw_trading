#!/usr/bin/env python3
"""
Daily evaluation script — evaluates trading strategies and updates checkpoints.

This script is run via cron to:
1. Evaluate strategy performance over the past 24 hours
2. Save model checkpoints with latest metrics
3. Update the leaderboard rankings
4. Log results for historical tracking
"""

import sys
import json
from datetime import datetime, UTC
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.leaderboard import Leaderboard
from src.evaluation.metrics import calculate_trade_stats, calculate_risk_metrics
from src.logging.performance_logger import PerformanceLogger


def main():
    print(f"[{datetime.now(UTC).isoformat()}] Starting daily evaluation...")

    # Initialize components
    perf_logger = PerformanceLogger(log_dir="logs/performance")
    leaderboard = Leaderboard(log_dir="logs/leaderboard", performance_logger=perf_logger)

    # Define agents (strategies + models) to track
    agents = [
        {"agent_id": "GridStrategy:v1", "agent_name": "GridStrategy", "agent_type": "strategy"},
        {"agent_id": "MeanReversionStrategy:v1", "agent_name": "MeanReversionStrategy", "agent_type": "strategy"},
        {"agent_id": "RSIBollingerStrategy:v1", "agent_name": "RSIBollingerStrategy", "agent_type": "strategy"},
        {"agent_id": "MomentumStrategy:v1", "agent_name": "MomentumStrategy", "agent_type": "strategy"},
        {"agent_id": "DNNInferenceModel:v1.0.0", "agent_name": "dnn", "agent_type": "model"},
    ]

    # Update rankings for last 24 hours
    print("Updating strategy rankings...")
    rankings = leaderboard.update_rankings(agents, period_days=1)

    if rankings:
        print(f"  Ranked {len(rankings)} agents:")
        for r in rankings:
            print(f"    #{r.rank} {r.agent_name}: P&L=${r.total_pnl:.2f}, Sharpe={r.sharpe_ratio:.2f}, Win Rate={r.win_rate:.1%}")
    else:
        print("  No rankings to update (no trade data yet)")

    # Update rankings for last 7 days
    print("\nUpdating 7-day rankings...")
    rankings_7d = leaderboard.update_rankings(agents, period_days=7)

    if rankings_7d:
        print(f"  7-day ranked {len(rankings_7d)} agents:")
        for r in rankings_7d[:5]:  # top 5
            print(f"    #{r.rank} {r.agent_name}: P&L=${r.total_pnl:.2f}, Sharpe={r.sharpe_ratio:.2f}")

    # Generate performance summary
    print("\nPerformance Summary (7-day):")
    perf_stats = perf_logger.get_performance_stats(days=7)
    if perf_stats:
        print(f"  Total P&L: ${perf_stats['total_pnl']:.2f}")
        print(f"  Total trades: {perf_stats['total_trades']}")
        print(f"  Win rate: {perf_stats['win_rate']:.1%}")
        print(f"  Avg P&L/day: ${perf_stats['avg_pnl_per_day']:.2f}")
    else:
        print("  No performance data available")

    # Get strategy comparison
    print("\nStrategy Comparison (7-day):")
    comparison = perf_logger.get_strategy_comparison(days=7)
    if "ranked_strategies" in comparison:
        for s in comparison["ranked_strategies"]:
            print(f"  #{s['rank']} {s['strategy']}: P&L=${s['total_pnl']:.2f}, Win Rate={s['win_rate']}, Sharpe={s['sharpe_ratio']}")

    print(f"\n[{datetime.now(UTC).isoformat()}] Daily evaluation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())