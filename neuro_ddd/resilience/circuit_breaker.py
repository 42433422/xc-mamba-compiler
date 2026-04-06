from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Circuit is open; fast-fail to protect downstream."""


class CircuitBreaker:
    """Simple three-state breaker (per process)."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._reset_timeout_s = reset_timeout_s
        self._half_open_max = max(1, half_open_max_calls)
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    def _maybe_transition_to_half_open(self) -> None:
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return
        if time.monotonic() - self._opened_at >= self._reset_timeout_s:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def allow(self) -> bool:
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                return False
            return self._half_open_calls < self._half_open_max

    def before_call(self) -> None:
        if not self.allow():
            raise CircuitOpenError("circuit breaker open")
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                return
            if self._failures >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
