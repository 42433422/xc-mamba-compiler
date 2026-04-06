"""Transactional outbox: persist-then-publish pattern for integration signals.

Swap ``InMemoryOutboxStore`` for a DB-backed implementation in production.
"""

from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from neuro_ddd.core.bus import NeuroBus
from neuro_ddd.core.delivery import BroadcastResult, DeliveryErrorPolicy
from neuro_ddd.core.signal import Signal


@dataclass
class OutboxRecord:
    record_id: str
    signal_envelope: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    last_error: Optional[str] = None


class OutboxStore(ABC):
    @abstractmethod
    def enqueue(self, signal_envelope: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    def pending(self) -> List[OutboxRecord]:
        pass

    @abstractmethod
    def mark_sent(self, record_id: str) -> None:
        pass

    @abstractmethod
    def mark_retry(self, record_id: str, error: BaseException) -> None:
        pass


class InMemoryOutboxStore(OutboxStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: Dict[str, OutboxRecord] = {}

    def enqueue(self, signal_envelope: Dict[str, Any]) -> str:
        rid = str(uuid.uuid4())
        rec = OutboxRecord(record_id=rid, signal_envelope=dict(signal_envelope))
        with self._lock:
            self._pending[rid] = rec
        return rid

    def pending(self) -> List[OutboxRecord]:
        with self._lock:
            return list(self._pending.values())

    def mark_sent(self, record_id: str) -> None:
        with self._lock:
            self._pending.pop(record_id, None)

    def mark_retry(self, record_id: str, error: BaseException) -> None:
        with self._lock:
            rec = self._pending.get(record_id)
            if rec is None:
                return
            rec.attempts += 1
            rec.last_error = repr(error)


@dataclass
class OutboxFlushResult:
    processed: int = 0
    failed: int = 0
    last_results: List[BroadcastResult] = field(default_factory=list)


class OutboxDispatcher:
    """Worker that delivers pending outbox rows through the bus (run from a job / after commit)."""

    def __init__(self, store: OutboxStore, bus: NeuroBus) -> None:
        self._store = store
        self._bus = bus

    def flush_pending(self) -> OutboxFlushResult:
        out = OutboxFlushResult()
        for rec in list(self._store.pending()):
            sig = Signal.from_dict(rec.signal_envelope)
            result = self._bus.broadcast(
                sig, error_policy=DeliveryErrorPolicy.ISOLATE
            )
            out.last_results.append(result)
            if result.ok():
                self._store.mark_sent(rec.record_id)
                out.processed += 1
            else:
                err = result.failures[0].error if result.failures else RuntimeError("unknown")
                self._store.mark_retry(rec.record_id, err)
                out.failed += 1
        return out
