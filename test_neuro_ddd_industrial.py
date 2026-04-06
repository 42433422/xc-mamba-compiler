"""Industrial features: event sourcing, resilience, tracing, config."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, ".")

from neuro_ddd import NeuroBus, Signal
from neuro_ddd.core.delivery import DeliveryErrorPolicy
from neuro_ddd.core.domain import NeuralDomain
from neuro_ddd.core.types import DomainType
from neuro_ddd.config import NeuroDddConfig
from neuro_ddd.ddd import DomainEvent, InMemoryRepository, NeuroUnitOfWork
from neuro_ddd.ddd.es_aggregate import EventSourcedAggregateRoot
from neuro_ddd.ddd.event_sourcing import ConcurrencyError, InMemoryEventStore
from neuro_ddd.observability.tracing import attach_trace_to_signal, structured_log_extra
from neuro_ddd.resilience import (
    BusResilience,
    CircuitBreaker,
    InMemoryDeadLetterQueue,
    RateLimitExceeded,
    TokenBucketRateLimiter,
)


class _Spy(NeuralDomain):
    def __init__(self, bus, dtype, fail: bool = False) -> None:
        self._fail = fail
        super().__init__(dtype, bus)

    def process_signal(self, signal):  # type: ignore[no-untyped-def]
        if self._fail:
            raise RuntimeError("boom")
        return None


class Counter(EventSourcedAggregateRoot):
    def __init__(self, cid: str) -> None:
        super().__init__(cid)
        self.total = 0

    def apply(self, event: DomainEvent) -> None:
        if event.name == "Added":
            self.total += int(event.payload.get("delta", 0))

    def add(self, delta: int) -> None:
        evt = DomainEvent(
            name="Added",
            aggregate_id=self.id,
            aggregate_type="Counter",
            payload={"delta": delta},
        )
        self.apply(evt)
        self._record(evt)


def test_event_store_append_and_replay() -> None:
    store = InMemoryEventStore()
    c = Counter("c1")
    c.add(3)
    c.add(2)
    evs = c.pull_domain_events()
    assert len(evs) == 2
    store.append("c1", "Counter", 0, evs)

    c2 = Counter("c1")
    c2.replay(store.load_stream("c1"))
    assert c2.total == 5
    assert c2._version == 2


def test_concurrency_error_on_bad_version() -> None:
    store = InMemoryEventStore()
    e = DomainEvent(name="Added", aggregate_id="x", aggregate_type="Counter", payload={"delta": 1})
    store.append("x", "Counter", 0, [e])
    with pytest.raises(ConcurrencyError):
        store.append("x", "Counter", 0, [e])


def test_uow_with_event_store() -> None:
    bus = NeuroBus(delivery_error_policy=DeliveryErrorPolicy.ISOLATE)
    _Spy(bus, DomainType.COMPILATION)
    bus.subscribe(DomainType.COMPILATION, "Added")
    repo: InMemoryRepository[Counter] = InMemoryRepository()
    store = InMemoryEventStore()
    uow = NeuroUnitOfWork(
        bus,
        source_domain=DomainType.SYMBOL_PERCEPTION,
        event_store=store,
    )
    uow.register_repository(Counter, repo)
    c = Counter("u1")
    c.add(10)
    uow.track(c)
    r = uow.commit()
    assert r.event_store_lengths == [1]
    assert store.stream_version("u1") == 1


def test_rate_limiter_blocks() -> None:
    rl = TokenBucketRateLimiter(capacity=1.0, refill_per_second=0.0)
    assert rl.try_acquire(1.0)
    with pytest.raises(RateLimitExceeded):
        rl.acquire_or_raise(1.0)


def test_bus_degrades_when_circuit_open_dlq() -> None:
    dlq = InMemoryDeadLetterQueue(max_entries=100)
    cb = CircuitBreaker(failure_threshold=1, reset_timeout_s=60.0)
    br = BusResilience(
        circuit_breaker=cb,
        dead_letter=dlq,
        on_circuit_open_return_empty=True,
    )
    bus = NeuroBus(resilience=br)
    sig = Signal(payload={})
    cb.record_failure()
    r = bus.broadcast(sig)
    assert r.delivered_domain_types == []
    assert any(x.reason == "circuit_open" for x in dlq.snapshot())


def test_signal_trace_and_structured_extra() -> None:
    s = Signal(name="e")
    attach_trace_to_signal(s)
    assert s.trace_id
    extra = structured_log_extra(s)
    assert extra["trace_id"] == s.trace_id


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEURO_DDD_RATE_CAPACITY", "42")
    c = NeuroDddConfig.from_env()
    assert c.rate_limit_capacity == 42.0


def test_cli_doctor_runs() -> None:
    from neuro_ddd.cli import cmd_doctor

    assert cmd_doctor() == 0
