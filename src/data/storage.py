"""Historical candle storage — persists candles to SQLite for backtesting."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .dataclasses import Candle


class CandleStorage:
    """Stores and retrieves historical candles from SQLite."""

    def __init__(self, db_path: Path | str = "logs/candles.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    UNIQUE(symbol, interval, timestamp)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_interval_time
                ON candles(symbol, interval, timestamp)
            """)

    def insert_candles(self, candles: Sequence[Candle], symbol: str, interval: str) -> int:
        """Insert a batch of candles. Returns number inserted."""
        rows = [
            (
                symbol, interval,
                c.timestamp.timestamp(), c.open, c.high, c.low, c.close, c.volume
            )
            for c in candles
        ]
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO candles
                   (symbol, interval, timestamp, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
            return conn.total_changes

    def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500
    ) -> list[Candle]:
        """Retrieve candles from storage."""
        query = "SELECT timestamp, open, high, low, close, volume FROM candles WHERE symbol=? AND interval=?"
        params: list = [symbol, interval]

        if start_time:
            query += " AND timestamp>=?"
            params.append(start_time.timestamp())
        if end_time:
            query += " AND timestamp<=?"
            params.append(end_time.timestamp())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [
            Candle(
                timestamp=datetime.fromtimestamp(r["timestamp"]),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
            )
            for r in reversed(rows)  # chronological order
        ]