from __future__ import annotations

from abc import ABC
from typing import List

from .events import DomainEvent


class AggregateRoot(ABC):
    """Consistency boundary: mutate via methods, record domain events, persist as one unit."""

    def __init__(self, aggregate_id: str) -> None:
        self._id = aggregate_id
        self._version: int = 0
        self._pending_events: List[DomainEvent] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> int:
        return self._version

    def _bump_version(self) -> None:
        self._version += 1

    def _record(self, event: DomainEvent) -> None:
        self._pending_events.append(event)

    def pull_domain_events(self) -> List[DomainEvent]:
        out = self._pending_events
        self._pending_events = []
        return out

    def mark_committed(self, new_version: int) -> None:
        """After successful persistence (e.g. event store append), set stream/snapshot version."""
        self._version = new_version


class Entity(ABC):
    def __init__(self, entity_id: str) -> None:
        self._entity_id = entity_id

    @property
    def entity_id(self) -> str:
        return self._entity_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._entity_id == other._entity_id

    def __hash__(self) -> int:
        return hash((self.__class__, self._entity_id))


class ValueObject(ABC):
    """Immutable value: prefer ``@dataclass(frozen=True, slots=True)`` + field validators."""

    def __eq__(self, other: object) -> bool:
        raise NotImplementedError

    def __hash__(self) -> int:
        raise NotImplementedError


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)
