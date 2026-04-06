"""Production-oriented delivery policies, results, and optional bus hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from .signal import Signal
from .types import DomainType


class DeliveryErrorPolicy(str, Enum):
    """How to handle handler exceptions during ``NeuroBus.broadcast``."""

    FAIL_FAST = "fail_fast"
    ISOLATE = "isolate"


class BroadcastTargetLimitExceeded(RuntimeError):
    """Raised when resolved subscribers exceed ``NeuroBus.max_targets_per_broadcast``."""

    def __init__(self, limit: int, actual: int) -> None:
        self.limit = limit
        self.actual = actual
        super().__init__(f"broadcast targets {actual} exceed limit {limit}")


class BroadcastLoopGuardTriggered(RuntimeError):
    """Raised when nested broadcasts repeat the same (topic, correlation) fingerprint too often."""

    def __init__(self, fingerprint: tuple[str, str], max_same: int) -> None:
        self.fingerprint = fingerprint
        self.max_same = max_same
        super().__init__(
            f"broadcast loop guard: fingerprint {fingerprint!r} nested more than {max_same} times"
        )


@dataclass
class DeliveryFailure:
    domain_type: DomainType
    signal_id: str
    signal_name: Optional[str]
    error: BaseException
    duration_ms: float = 0.0


class DomainDeliveryStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"


@dataclass
class DomainDeliveryRecord:
    """One handler invocation within a broadcast (for tracing / post-mortems)."""

    domain_type: DomainType
    status: DomainDeliveryStatus
    duration_ms: float
    error: Optional[BaseException] = None


@dataclass
class BroadcastResult:
    failures: List[DeliveryFailure] = field(default_factory=list)
    delivered_domain_types: List[DomainType] = field(default_factory=list)
    resolved_domain_types: List[DomainType] = field(default_factory=list)
    attempts: List[DomainDeliveryRecord] = field(default_factory=list)

    def ok(self) -> bool:
        return len(self.failures) == 0

    def partial_success(self) -> bool:
        return bool(self.delivered_domain_types and self.failures)

    def raise_first(self) -> None:
        if self.failures:
            raise self.failures[0].error

    @property
    def not_attempted_domain_types(self) -> List[DomainType]:
        tried = {a.domain_type for a in self.attempts}
        return [d for d in self.resolved_domain_types if d not in tried]


OnBroadcastBegin = Callable[[Signal], None]
OnBroadcastEnd = Callable[[Signal, "BroadcastResult"], None]
OnHandlerError = Callable[[Signal, DomainType, BaseException], None]
OnPartialFailure = Callable[[Signal, "BroadcastResult"], None]


@dataclass
class BusHooks:
    """Optional observability / tracing hooks (keep handlers fast and non-blocking)."""

    on_broadcast_begin: Optional[OnBroadcastBegin] = None
    on_broadcast_end: Optional[OnBroadcastEnd] = None
    on_handler_error: Optional[OnHandlerError] = None
    on_partial_failure: Optional[OnPartialFailure] = None
