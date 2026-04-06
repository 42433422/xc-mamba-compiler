from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from neuro_ddd.core.types import DomainType


@dataclass
class DeadLetterEntry:
    signal_envelope: Dict[str, Any]
    reason: str
    domain_type: Optional[DomainType] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class InMemoryDeadLetterQueue:
    """Last-line-of-defense queue for failed or rejected deliveries (in-memory)."""

    def __init__(self, *, max_entries: int = 10_000) -> None:
        self._max = max_entries
        self._lock = threading.RLock()
        self._items: List[DeadLetterEntry] = []

    def push(
        self,
        *,
        signal_envelope: Dict[str, Any],
        reason: str,
        domain_type: Optional[DomainType] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        entry = DeadLetterEntry(
            signal_envelope=dict(signal_envelope),
            reason=reason,
            domain_type=domain_type,
            error=repr(error) if error else None,
        )
        with self._lock:
            self._items.append(entry)
            overflow = len(self._items) - self._max
            if overflow > 0:
                del self._items[0:overflow]

    def snapshot(self) -> List[DeadLetterEntry]:
        with self._lock:
            return list(self._items)
