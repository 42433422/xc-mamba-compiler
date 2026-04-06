from __future__ import annotations

import threading
import time


class RateLimitExceeded(Exception):
    """Token bucket exhausted."""


class TokenBucketRateLimiter:
    """Fixed-capacity token bucket refilled continuously (thread-safe)."""

    def __init__(self, *, capacity: float, refill_per_second: float) -> None:
        self._capacity = float(capacity)
        self._refill_rate = float(refill_per_second)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = threading.RLock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(
            self._capacity, self._tokens + elapsed * self._refill_rate
        )

    def try_acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def acquire_or_raise(self, tokens: float = 1.0) -> None:
        if not self.try_acquire(tokens):
            raise RateLimitExceeded("rate limit exceeded")
