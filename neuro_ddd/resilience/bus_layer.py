from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .dead_letter import InMemoryDeadLetterQueue
from .rate_limit import RateLimitExceeded, TokenBucketRateLimiter


@dataclass
class BusResilience:
    """Optional bundle wired into ``NeuroBus``: limit -> circuit -> DLQ on degrade/fail."""

    rate_limiter: Optional[TokenBucketRateLimiter] = None
    circuit_breaker: Optional[CircuitBreaker] = None
    dead_letter: Optional[InMemoryDeadLetterQueue] = None
    on_circuit_open_return_empty: bool = True

    def before_broadcast(self, signal_dict: dict) -> None:
        if self.rate_limiter is not None:
            self.rate_limiter.acquire_or_raise()
        if self.circuit_breaker is not None:
            self.circuit_breaker.before_call()

    def record_broadcast_success(self) -> None:
        if self.circuit_breaker is not None:
            self.circuit_breaker.record_success()

    def record_broadcast_failure(self, exc: BaseException) -> None:
        if self.circuit_breaker is None:
            return
        self.circuit_breaker.record_failure()

    def handle_circuit_open(self, signal_dict: dict) -> None:
        if self.dead_letter is not None:
            self.dead_letter.push(
                signal_envelope=signal_dict,
                reason="circuit_open",
            )

    def handle_rate_limit(self, signal_dict: dict, exc: RateLimitExceeded) -> None:
        if self.dead_letter is not None:
            self.dead_letter.push(
                signal_envelope=signal_dict,
                reason="rate_limited",
                error=exc,
            )
