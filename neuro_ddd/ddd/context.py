from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

from neuro_ddd.core.signal import Signal
from neuro_ddd.core.types import DomainType

from .events import DomainEvent, envelope_for_bus


class ContextRelation(Enum):
    """Strategic DDD: how this context relates to another (simplified)."""

    PARTNERSHIP = "partnership"
    CUSTOMER_SUPPLIER = "customer_supplier"
    CONFORMIST = "conformist"
    ANTICORRUPTION = "anticorruption"
    OPEN_HOST = "open_host"


@dataclass
class BoundedContext:
    """Named boundary for ubiquitous language and ownership."""

    name: str
    domain_type: Optional[DomainType] = None
    description: str = ""
    publishes: Set[str] = field(default_factory=set)
    subscribes: Set[str] = field(default_factory=set)


AclTranslator = Callable[[DomainEvent], Optional[DomainEvent]]


@dataclass
class ContextMap:
    """Registers contexts and optional ACL translators on inbound integration events."""

    contexts: Dict[str, BoundedContext] = field(default_factory=dict)
    _inbound_acl: Dict[tuple[str, str], AclTranslator] = field(default_factory=dict)

    def register(self, ctx: BoundedContext) -> None:
        self.contexts[ctx.name] = ctx

    def add_acl(
        self,
        from_context: str,
        event_name: str,
        translator: AclTranslator,
    ) -> None:
        self._inbound_acl[(from_context, event_name)] = translator

    def translate_inbound(
        self, from_context: str, event: DomainEvent
    ) -> Optional[DomainEvent]:
        key = (from_context, event.name)
        fn = self._inbound_acl.get(key)
        if fn is None:
            return event
        return fn(event)


def integration_event_from_signal(signal: Signal) -> DomainEvent | None:
    """Parse a bus ``Signal`` carrying ``envelope_for_bus`` payload (integration event)."""
    if not signal.name:
        return None
    p = signal.payload
    if not isinstance(p, dict) or "event_id" not in p:
        return None
    return DomainEvent.from_bus_envelope(p)


def signal_from_integration_event(
    evt: DomainEvent,
    *,
    source_domain: Optional[DomainType] = None,
    target_domains: Optional[List[DomainType]] = None,
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
) -> Signal:
    return Signal(
        signal_type=None,
        source_domain=source_domain,
        target_domains=list(target_domains or []),
        name=evt.name,
        payload=envelope_for_bus(evt),
        correlation_id=correlation_id or evt.event_id,
        causation_id=causation_id,
    )
