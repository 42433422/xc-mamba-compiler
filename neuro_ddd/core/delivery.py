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


@dataclass
class DeliveryFailure:
    domain_type: DomainType
    signal_id: str
    signal_name: Optional[str]
    error: BaseException


@dataclass
class BroadcastResult:
    failures: List[DeliveryFailure] = field(default_factory=list)
    delivered_domain_types: List[DomainType] = field(default_factory=list)

    def ok(self) -> bool:
        return len(self.failures) == 0

    def raise_first(self) -> None:
        if self.failures:
            raise self.failures[0].error


OnBroadcastBegin = Callable[[Signal], None]
OnBroadcastEnd = Callable[[Signal, BroadcastResult], None]
OnHandlerError = Callable[[Signal, DomainType, BaseException], None]


@dataclass
class BusHooks:
    """Optional observability / tracing hooks (keep handlers fast and non-blocking)."""

    on_broadcast_begin: Optional[OnBroadcastBegin] = None
    on_broadcast_end: Optional[OnBroadcastEnd] = None
    on_handler_error: Optional[OnHandlerError] = None
