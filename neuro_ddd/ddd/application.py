from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, Generic, List, Optional, TypeVar

from neuro_ddd.core.bus import NeuroBus
from neuro_ddd.core.types import DomainType

from .aggregate import AggregateRoot
from .context import signal_from_integration_event
from .event_sourcing import EventStore
from .events import DomainEvent
from .outbox import OutboxStore
from .repository import Repository

TAgg = TypeVar("TAgg", bound=AggregateRoot)
TCommand = TypeVar("TCommand")
TResult = TypeVar("TResult")

OutboundMap = Callable[[DomainEvent], Optional[DomainEvent]]


@dataclass
class CommitResult:
    published_event_names: List[str]
    outbox_record_ids: List[str]
    event_store_lengths: List[int]


class UnitOfWork(ABC):
    """Transaction boundary: persist aggregates then publish integration signals."""

    @abstractmethod
    def commit(self) -> CommitResult:
        pass


class NeuroUnitOfWork(UnitOfWork):
    """Tracks dirty aggregates, saves repositories, publishes domain events on the bus."""

    def __init__(
        self,
        bus: NeuroBus,
        *,
        source_domain: Optional[DomainType] = None,
        map_outbound: Optional[OutboundMap] = None,
        outbox: Optional[OutboxStore] = None,
        event_store: Optional[EventStore] = None,
    ) -> None:
        self._bus = bus
        self._source_domain = source_domain
        self._map_outbound = map_outbound
        self._outbox = outbox
        self._event_store = event_store
        self._repos: Dict[type, Repository] = {}
        self._dirty: List[AggregateRoot] = []

    def register_repository(self, aggregate_cls: type, repo: Repository) -> None:
        self._repos[aggregate_cls] = repo

    def track(self, aggregate: AggregateRoot) -> None:
        if aggregate not in self._dirty:
            self._dirty.append(aggregate)

    def _save_aggregate(self, aggregate: AggregateRoot) -> None:
        repo = self._repos.get(type(aggregate))
        if repo is None:
            raise KeyError(f"No repository registered for {type(aggregate).__name__}")
        repo.save(aggregate)

    def commit(self) -> CommitResult:
        names: List[str] = []
        outbox_ids: List[str] = []
        stream_lens: List[int] = []
        for agg in list(self._dirty):
            events = agg.pull_domain_events()
            if self._event_store is not None and events:
                exp = self._event_store.stream_version(agg.id)
                agg_type = type(agg).__name__
                new_len = self._event_store.append(agg.id, agg_type, exp, events)
                agg.mark_committed(new_len)
                stream_lens.append(new_len)
            self._save_aggregate(agg)
            for evt in events:
                mapped: Optional[DomainEvent] = evt
                if self._map_outbound is not None:
                    mapped = self._map_outbound(evt)
                if mapped is None:
                    continue
                sig = signal_from_integration_event(
                    mapped,
                    source_domain=self._source_domain,
                    correlation_id=mapped.event_id,
                )
                if self._outbox is not None:
                    outbox_ids.append(self._outbox.enqueue(sig.to_dict()))
                else:
                    self._bus.broadcast(sig)
                names.append(mapped.name)
        self._dirty.clear()
        return CommitResult(
            published_event_names=names,
            outbox_record_ids=outbox_ids,
            event_store_lengths=stream_lens,
        )


class CommandHandler(ABC, Generic[TCommand, TResult]):
    @abstractmethod
    def __call__(self, command: TCommand) -> TResult:
        pass


def handler(
    fn: Callable[[TCommand], TResult],
) -> CommandHandler[TCommand, TResult]:
    class _H(CommandHandler[TCommand, TResult]):
        def __call__(self, command: TCommand) -> TResult:
            return fn(command)

    return _H()
