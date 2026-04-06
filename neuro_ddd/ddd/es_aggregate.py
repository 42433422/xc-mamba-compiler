"""Event-sourced aggregate: state changes only via ``apply`` + recorded events."""

from __future__ import annotations

from abc import abstractmethod
from typing import Iterable, List

from .aggregate import AggregateRoot
from .event_sourcing import StoredEvent
from .events import DomainEvent


class EventSourcedAggregateRoot(AggregateRoot):
    """Rebuild state with ``replay``; business commands call ``_record`` after ``apply``."""

    def replay(self, history: Iterable[StoredEvent]) -> None:
        self._pending_events.clear()
        for row in history:
            self.apply(row.event)
            self._version = row.stream_version

    def replay_from_events(self, events: Iterable[DomainEvent]) -> None:
        self._pending_events.clear()
        v = 0
        for evt in events:
            v += 1
            self.apply(evt)
            self._version = v

    @abstractmethod
    def apply(self, event: DomainEvent) -> None:
        """Update internal state from a persisted event (no side I/O)."""

    def expected_stream_version(self) -> int:
        """Cached stream length after ``replay``; use store.stream_version(id) at commit when in doubt."""
        return self._version
