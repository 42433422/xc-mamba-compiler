"""
Tests for neuro_ddd DDD layer: aggregates, UoW, topic routing, integration envelopes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, ".")

from neuro_ddd.core.bus import NeuroBus
from neuro_ddd.core.domain import NeuralDomain
from neuro_ddd.core.signal import Signal
from neuro_ddd.core.types import DomainType
from neuro_ddd.core.delivery import BusHooks, DeliveryErrorPolicy
from neuro_ddd.ddd import (
    ContextMap,
    DomainEvent,
    InMemoryOutboxStore,
    InMemoryRepository,
    NeuroUnitOfWork,
    OutboxDispatcher,
    ensure,
    integration_event_from_signal,
    signal_from_integration_event,
)
from neuro_ddd.ddd.aggregate import AggregateRoot


class _SpyDomain(NeuralDomain):
    def __init__(self, bus: NeuroBus, domain_type: DomainType) -> None:
        self.received: list[Signal] = []
        super().__init__(domain_type, bus)

    def process_signal(self, signal):  # type: ignore[no-untyped-def]
        self.received.append(signal)
        return None


class Order(AggregateRoot):
    def __init__(self, order_id: str) -> None:
        super().__init__(order_id)
        self._lines: int = 0

    def add_line(self) -> None:
        self._lines += 1
        self._bump_version()
        self._record(
            DomainEvent(
                name="OrderLineAdded",
                aggregate_id=self.id,
                aggregate_type="Order",
                payload={"lines": self._lines},
            )
        )

    def place(self) -> None:
        ensure(self._lines > 0, "order must have lines")
        self._bump_version()
        self._record(
            DomainEvent(
                name="OrderPlaced",
                aggregate_id=self.id,
                aggregate_type="Order",
                payload={"lines": self._lines},
            )
        )


@dataclass
class PlaceOrder:
    order_id: str


def test_topic_routing_delivers_only_to_subscribers() -> None:
    bus = NeuroBus()
    sym = _SpyDomain(bus, DomainType.SYMBOL_PERCEPTION)
    comp = _SpyDomain(bus, DomainType.COMPILATION)
    bus.subscribe(DomainType.COMPILATION, "OrderPlaced")

    sig = Signal(
        name="OrderPlaced",
        source_domain=DomainType.SYMBOL_PERCEPTION,
        payload={"x": 1},
    )
    bus.broadcast(sig)

    assert len(sym.received) == 0
    assert len(comp.received) == 1
    assert comp.received[0].name == "OrderPlaced"


def test_explicit_target_domains_override_broadcast() -> None:
    bus = NeuroBus()
    _SpyDomain(bus, DomainType.SYMBOL_PERCEPTION)
    comp = _SpyDomain(bus, DomainType.COMPILATION)
    sec = _SpyDomain(bus, DomainType.SECURITY_VERIFICATION)

    sig = Signal(
        source_domain=DomainType.SYMBOL_PERCEPTION,
        target_domains=[DomainType.SECURITY_VERIFICATION],
        payload={},
    )
    bus.broadcast(sig)

    assert len(comp.received) == 0
    assert len(sec.received) == 1


def test_send_command_requires_single_target() -> None:
    bus = NeuroBus()
    _SpyDomain(bus, DomainType.COMPILATION)

    with pytest.raises(ValueError):
        bus.send_command(
            Signal(
                source_domain=DomainType.SYMBOL_PERCEPTION,
                target_domains=[],
                payload={},
            )
        )


def test_neuro_unit_of_work_commit_publishes_integration_events() -> None:
    bus = NeuroBus()
    inv = _SpyDomain(bus, DomainType.COMPILATION)
    bus.subscribe(DomainType.COMPILATION, "OrderPlaced")

    repo: InMemoryRepository[Order] = InMemoryRepository()
    uow = NeuroUnitOfWork(bus, source_domain=DomainType.SYMBOL_PERCEPTION)
    uow.register_repository(Order, repo)

    order = Order("o1")
    order.add_line()
    order.place()
    uow.track(order)

    result = uow.commit()
    assert result.outbox_record_ids == []
    assert result.event_store_lengths == []
    assert "OrderPlaced" in result.published_event_names
    assert "OrderLineAdded" in result.published_event_names
    assert len(inv.received) >= 1
    placed = [s for s in inv.received if s.name == "OrderPlaced"]
    assert len(placed) == 1
    evt = integration_event_from_signal(placed[0])
    assert evt is not None
    assert evt.aggregate_id == "o1"


def test_integration_event_roundtrip_envelope() -> None:
    evt = DomainEvent(
        name="X",
        aggregate_id="a1",
        aggregate_type="A",
        payload={"k": "v"},
    )
    sig = signal_from_integration_event(evt, source_domain=DomainType.DYNAMIC_SCHEDULING)
    back = integration_event_from_signal(sig)
    assert back is not None
    assert back.name == "X"
    assert back.payload == {"k": "v"}


def test_signal_from_dict_roundtrip() -> None:
    s = Signal(
        name="Evt",
        source_domain=DomainType.SYMBOL_PERCEPTION,
        payload={"k": 1},
        correlation_id="c1",
    )
    s2 = Signal.from_dict(s.to_dict())
    assert s2.name == "Evt"
    assert s2.correlation_id == "c1"
    assert s2.source_domain == DomainType.SYMBOL_PERCEPTION
    assert s2.payload == {"k": 1}


def test_delivery_isolate_continues_after_handler_error() -> None:
    bus = NeuroBus(delivery_error_policy=DeliveryErrorPolicy.ISOLATE)
    ok_a = _SpyDomain(bus, DomainType.SYMBOL_PERCEPTION)
    bad = _SpyDomain(bus, DomainType.COMPILATION)
    ok_b = _SpyDomain(bus, DomainType.SECURITY_VERIFICATION)

    def bad_process(signal):  # type: ignore[no-untyped-def]
        raise RuntimeError("handler down")

    bad.process_signal = bad_process  # type: ignore[method-assign]

    sig = Signal(payload={}, source_domain=DomainType.DYNAMIC_SCHEDULING)
    result = bus.broadcast(sig)
    assert not result.ok()
    assert len(result.failures) == 1
    assert len(ok_a.received) == 1
    assert len(ok_b.received) == 1


def test_outbox_commit_then_flush_delivers() -> None:
    store = InMemoryOutboxStore()
    bus = NeuroBus()
    inv = _SpyDomain(bus, DomainType.COMPILATION)
    bus.subscribe(DomainType.COMPILATION, "OrderPlaced")

    repo: InMemoryRepository[Order] = InMemoryRepository()
    uow = NeuroUnitOfWork(
        bus,
        source_domain=DomainType.SYMBOL_PERCEPTION,
        outbox=store,
    )
    uow.register_repository(Order, repo)
    order = Order("o-outbox")
    order.add_line()
    order.place()
    uow.track(order)
    result = uow.commit()
    assert len(result.outbox_record_ids) == 2
    assert len(inv.received) == 0

    flush = OutboxDispatcher(store, bus).flush_pending()
    assert flush.processed == 2
    assert flush.failed == 0
    placed = [s for s in inv.received if s.name == "OrderPlaced"]
    assert len(placed) == 1


def test_max_dispatch_depth_limits_reentrant_broadcast() -> None:
    bus_holder: list[NeuroBus] = []

    def reenter(sig):  # type: ignore[no-untyped-def]
        bus_holder[0].broadcast(Signal(payload={"inner": True}))

    bus = NeuroBus(max_dispatch_depth=3, hooks=BusHooks(on_broadcast_begin=reenter))
    bus_holder.append(bus)
    with pytest.raises(RuntimeError, match="dispatch depth"):
        bus.broadcast(Signal(payload={"root": True}))


def test_context_map_acl_inbound() -> None:
    cm = ContextMap()
    cm.add_acl(
        "Orders",
        "OrderPlaced",
        lambda e: DomainEvent(
            name="StockReservationRequested",
            aggregate_id=e.aggregate_id,
            aggregate_type="Stock",
            payload=dict(e.payload),
        ),
    )
    original = DomainEvent(
        name="OrderPlaced",
        aggregate_id="o1",
        aggregate_type="Order",
        payload={"lines": 2},
    )
    mapped = cm.translate_inbound("Orders", original)
    assert mapped is not None
    assert mapped.name == "StockReservationRequested"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
