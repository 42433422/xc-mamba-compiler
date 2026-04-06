from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Generic, Optional, TypeVar

from .aggregate import AggregateRoot

TAgg = TypeVar("TAgg", bound=AggregateRoot)


class Repository(ABC, Generic[TAgg]):
    @abstractmethod
    def get_by_id(self, aggregate_id: str) -> Optional[TAgg]:
        pass

    @abstractmethod
    def save(self, aggregate: TAgg) -> None:
        pass


class InMemoryRepository(Repository[TAgg], Generic[TAgg]):
    def __init__(self) -> None:
        self._store: Dict[str, TAgg] = {}

    def get_by_id(self, aggregate_id: str) -> Optional[TAgg]:
        return self._store.get(aggregate_id)

    def save(self, aggregate: TAgg) -> None:
        self._store[aggregate.id] = aggregate
