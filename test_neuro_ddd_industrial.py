"""Industrial features: event sourcing, resilience, tracing, config."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, ".")

from neuro_ddd import NeuroBus, Signal
from neuro_ddd.core.delivery import (
    BroadcastLoopGuardTriggered,
    BroadcastTargetLimitExceeded,
    BusHooks,
    DeliveryErrorPolicy,
    DomainDeliveryStatus,
)
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


def test_broadcast_result_attempts_and_resolved() -> None:
    bus = NeuroBus(delivery_error_policy=DeliveryErrorPolicy.ISOLATE)
    _Spy(bus, DomainType.COMPILATION)
    _Spy(bus, DomainType.SECURITY_VERIFICATION)
    r = bus.broadcast(Signal(source_domain=DomainType.SYMBOL_PERCEPTION, payload={}))
    assert len(r.resolved_domain_types) == 2
    assert len(r.attempts) == 2
    assert all(a.status == DomainDeliveryStatus.OK for a in r.attempts)


def test_max_targets_per_broadcast() -> None:
    bus = NeuroBus(max_targets_per_broadcast=1)
    _Spy(bus, DomainType.COMPILATION)
    _Spy(bus, DomainType.SECURITY_VERIFICATION)
    with pytest.raises(BroadcastTargetLimitExceeded):
        bus.broadcast(Signal(source_domain=DomainType.SYMBOL_PERCEPTION, payload={}))


def test_loop_guard_same_fingerprint() -> None:
    class Bouncer(NeuralDomain):
        def __init__(self, bus, dtype: DomainType, bounce_to: DomainType) -> None:
            self._to = bounce_to
            super().__init__(dtype, bus)

        def process_signal(self, signal):  # type: ignore[no-untyped-def]
            return Signal(
                name=signal.name,
                correlation_id=signal.correlation_id,
                source_domain=self.domain_type,
                target_domains=[self._to],
                payload=signal.payload,
            )

    bus = NeuroBus(loop_guard_max_same_fingerprint=2)
    Bouncer(bus, DomainType.COMPILATION, DomainType.SECURITY_VERIFICATION)
    Bouncer(bus, DomainType.SECURITY_VERIFICATION, DomainType.COMPILATION)
    sig = Signal(
        name="ping",
        correlation_id="one-chain",
        source_domain=DomainType.SYMBOL_PERCEPTION,
        target_domains=[DomainType.COMPILATION],
        payload={},
    )
    with pytest.raises(BroadcastLoopGuardTriggered):
        bus.broadcast(sig)


def test_on_partial_failure_hook() -> None:
    bag: list = []

    bus = NeuroBus(
        delivery_error_policy=DeliveryErrorPolicy.ISOLATE,
        hooks=BusHooks(
            on_partial_failure=lambda s, res: bag.append(
                (s.signal_id, res.partial_success(), len(res.failures))
            )
        ),
    )
    _Spy(bus, DomainType.COMPILATION)
    _Spy(bus, DomainType.SECURITY_VERIFICATION, fail=True)
    bus.broadcast(Signal(source_domain=DomainType.SYMBOL_PERCEPTION, payload={}))
    assert len(bag) == 1
    assert bag[0][1] is True
    assert bag[0][2] == 1


def test_signal_derive_and_domain_inherit_trace() -> None:
    parent = Signal(name="topic", correlation_id="corr-1")
    attach_trace_to_signal(parent)
    child = parent.derive(name="child_topic", payload={"x": 2})
    assert child.causation_id == parent.signal_id
    assert child.correlation_id == parent.correlation_id
    assert child.trace_id == parent.trace_id

    class Forward(NeuralDomain):
        def __init__(self, bus, dtype: DomainType, to: DomainType) -> None:
            self._to = to
            super().__init__(dtype, bus)

        def process_signal(self, signal):  # type: ignore[no-untyped-def]
            return Signal(target_domains=[self._to], payload={"n": 1})

    class SpyRecv(NeuralDomain):
        def __init__(self, bus, dtype: DomainType) -> None:
            self.received: list = []
            super().__init__(dtype, bus)

        def process_signal(self, signal):  # type: ignore[no-untyped-def]
            self.received.append(signal)
            return None

    bus = NeuroBus()
    Forward(bus, DomainType.COMPILATION, DomainType.SECURITY_VERIFICATION)
    sec = SpyRecv(bus, DomainType.SECURITY_VERIFICATION)
    bus.broadcast(
        Signal(
            name="in",
            correlation_id="trace-me",
            source_domain=DomainType.SYMBOL_PERCEPTION,
            target_domains=[DomainType.COMPILATION],
            payload={},
        )
    )
    assert len(sec.received) == 1
    assert sec.received[0].correlation_id == "trace-me"
    assert sec.received[0].causation_id is not None


def test_serialize_broadcasts_no_interleave() -> None:
    import threading

    order: list[int] = []
    lock = threading.Lock()

    class Tag(NeuralDomain):
        def __init__(self, bus, dtype: DomainType, tag: int) -> None:
            self._tag = tag
            super().__init__(dtype, bus)

        def process_signal(self, signal):  # type: ignore[no-untyped-def]
            with lock:
                order.append(self._tag)
            return None

    bus = NeuroBus(serialize_broadcasts=True)
    Tag(bus, DomainType.COMPILATION, 1)
    Tag(bus, DomainType.SECURITY_VERIFICATION, 2)

    def run(tag: int) -> None:
        bus.broadcast(
            Signal(
                source_domain=DomainType.SYMBOL_PERCEPTION,
                target_domains=[DomainType.COMPILATION, DomainType.SECURITY_VERIFICATION],
                payload={"t": tag},
            )
        )

    t1 = threading.Thread(target=run, args=(1,))
    t2 = threading.Thread(target=run, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len(order) == 4
