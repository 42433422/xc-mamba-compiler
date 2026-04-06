"""Event store + event-sourced aggregate replay (optimistic concurrency)."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import DomainEvent, envelope_for_bus


class ConcurrencyError(Exception):
    """Stream version mismatch on append."""


@dataclass
class StoredEvent:
    """Single persisted domain event in a stream."""

    stream_version: int
    aggregate_id: str
    aggregate_type: str
    event: DomainEvent


class EventStore(ABC):
    @abstractmethod
    def load_stream(self, aggregate_id: str) -> List[StoredEvent]:
        pass

    @abstractmethod
    def append(
        self,
        aggregate_id: str,
        aggregate_type: str,
        expected_version: int,
        events: List[DomainEvent],
    ) -> int:
        """Append events; ``expected_version`` is current stream length. Returns new length."""

    @abstractmethod
    def stream_version(self, aggregate_id: str) -> int:
        pass


class InMemoryEventStore(EventStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._streams: Dict[str, List[StoredEvent]] = {}

    def load_stream(self, aggregate_id: str) -> List[StoredEvent]:
        with self._lock:
            return list(self._streams.get(aggregate_id, ()))

    def stream_version(self, aggregate_id: str) -> int:
        with self._lock:
            return len(self._streams.get(aggregate_id, ()))

    def append(
        self,
        aggregate_id: str,
        aggregate_type: str,
        expected_version: int,
        events: List[DomainEvent],
    ) -> int:
        if not events:
            return self.stream_version(aggregate_id)
        with self._lock:
            stream = self._streams.setdefault(aggregate_id, [])
            if len(stream) != expected_version:
                raise ConcurrencyError(
                    f"aggregate={aggregate_id!r} expected_version={expected_version} "
                    f"actual={len(stream)}"
                )
            start = len(stream) + 1
            for i, evt in enumerate(events):
                stream.append(
                    StoredEvent(
                        stream_version=start + i,
                        aggregate_id=aggregate_id,
                        aggregate_type=aggregate_type,
                        event=evt,
                    )
                )
            return len(stream)
