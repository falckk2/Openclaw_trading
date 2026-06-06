"""In-memory data cache with TTL support."""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """A cached value with expiration time."""
    value: Any
    expires_at: float


class DataCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self):
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        """Get a cached value if it exists and hasn't expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set a cached value with a TTL in seconds."""
        self._store[key] = CacheEntry(
            value=value,
            expires_at=time.time() + ttl
        )

    def delete(self, key: str) -> None:
        """Delete a cached value."""
        self._store.pop(key, None)

    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = time.time()
        expired_keys = [
            k for k, v in self._store.items()
            if now > v.expires_at
        ]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)

    def clear_all(self) -> None:
        """Clear all cached entries."""
        self._store.clear()