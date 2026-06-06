"""Market data fetcher — pulls data from exchange and feeds to strategies."""

import asyncio
from typing import AsyncIterator

from ..exchange.base import ExchangeClient
from .dataclasses import Candle, Ticker
from .cache import DataCache


class DataFetcher:
    """Fetches and caches market data from an exchange."""

    def __init__(self, exchange: ExchangeClient, cache: DataCache | None = None):
        self._exchange = exchange
        self._cache = cache or DataCache()

    async def get_candles(self, symbol: str, interval: str, limit: int = 100) -> list[Candle]:
        """Get historical candles, using cache when possible."""
        cache_key = f"candles:{symbol}:{interval}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        candles = await self._exchange.get_candles(symbol, interval, limit)
        self._cache.set(cache_key, candles, ttl=60)  # 60s cache
        return candles

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current ticker."""
        return await self._exchange.get_ticker(symbol)

    async def stream_candles(self, symbol: str, interval: str) -> AsyncIterator[Candle]:
        """Stream live candles from exchange WebSocket."""
        async for candle in self._exchange.stream_candles(symbol, interval):
            yield candle

    def get_cached_candles(self, symbol: str, interval: str, limit: int = 100) -> list[Candle] | None:
        """Get cached candles if available."""
        cache_key = f"candles:{symbol}:{interval}:{limit}"
        return self._cache.get(cache_key)