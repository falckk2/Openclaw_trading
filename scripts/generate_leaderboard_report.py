#!/usr/bin/env python3
"""
Weekly leaderboard report generator.

This script is run via cron to:
1. Generate comprehensive weekly leaderboard report
2. Save report to logs/leaderboard/
3. Send summary to Telegram
"""

import sys
import json
from datetime import datetime, UTC
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.leaderboard import Leaderboard
from src.logging.performance_logger import PerformanceLogger


def generate_text_report(report: dict) -> str:
    """Generate a human-readable text report from the report dict."""
    lines = ["📊 **Weekly Trading Agent Leaderboard**\n"]

    lines.append(f"**Report Date:** {report.get('report_date', 'N/A')}")
    lines.append(f"**Period:** Last {report.get('period_days', 7)} days")
    lines.append(f"**Total Agents:** {report.get('total_agents', 0)}\n")

    # Top 3
    lines.append("🏆 **Top 3 Agents:**")
    for agent in report.get("top_3", []):
        lines.append(f"  #{agent['rank']} {agent['agent']}: ${agent['pnl']:.2f}")
    lines.append("")

    # Highlights
    highlights = report.get("highlights", {})
    lines.append("⭐ **Highlights:**")
    lines.append(f"  Best by P&L: {highlights.get('best_by_pnl', {}).get('agent', 'N/A')} (${highlights.get('best_by_pnl', {}).get('pnl', 0):.2f})")
    lines.append(f"  Best Sharpe: {highlights.get('best_by_sharpe', {}).get('agent', 'N/A')} ({highlights.get('best_by_sharpe', {}).get('sharpe', 0):.2f})")
    lines.append(f"  Most Active: {highlights.get('most_active', {}).get('agent', 'N/A')} ({highlights.get('most_active', {}).get('trades', 0)} trades)")
    lines.append(f"  Best Win Rate: {highlights.get('best_win_rate', {}).get('agent', 'N/A')} ({highlights.get('best_win_rate', {}).get('win_rate', 'N/A')})")
    lines.append("")

    # Trends
    trends = report.get("trends", {})
    improving = trends.get("improving", [])
    declining = trends.get("declining", [])

    if improving:
        lines.append("📈 **Improving:** " + ", ".join(improving))
    if declining:
        lines.append("📉 **Declining:** " + ", ".join(declining))

    lines.append("")
    lines.append("📋 **Full Rankings:**")
    for r in report.get("rankings", []):
        status = "🟢" if r["trend"] == "up" else ("🔴" if r["trend"] == "down" else "⚪️")
        lines.append(
            f"  {status} #{r['rank']} {r['agent_name']}: "
            f"P&L=${r['total_pnl']:.2f}, "
            f"Win={r['win_rate']:.0%}, "
            f"Sharpe={r['sharpe_ratio']:.2f}, "
            f"Trades={r['num_trades']}"
        )

    return "\n".join(lines)


def main():
    print(f"[{datetime.now(UTC).isoformat()}] Generating weekly leaderboard report...")

    # Initialize components
    perf_logger = PerformanceLogger(log_dir="logs/performance")
    leaderboard = Leaderboard(log_dir="logs/leaderboard", performance_logger=perf_logger)

    # Generate report for last 7 days
    report = leaderboard.generate_report(period_days=7)

    if "error" in report:
        print(f"  Error generating report: {report['error']}")
        return 1

    # Save report
    report_path = leaderboard.save_report(report, name="weekly")
    print(f"  Report saved to: {report_path}")

    # Generate text version
    text_report = generate_text_report(report)
    print("\n" + text_report)

    # Save text version too
    text_path = leaderboard._log_dir / f"report_weekly_{datetime.now(UTC).strftime('%Y%m%d')}.txt"
    with open(text_path, "w") as f:
        f.write(text_report)
    print(f"\nText report saved to: {text_path}")

    print(f"\n[{datetime.now(UTC).isoformat()}] Weekly report generation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())