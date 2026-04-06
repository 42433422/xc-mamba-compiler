from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, cast


@dataclass(frozen=True)
class DomainEvent:
    """Something that happened inside a model; publish after the aggregate is persisted."""

    name: str
    aggregate_id: str
    aggregate_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def with_payload(self, **extra: Any) -> "DomainEvent":
        merged: dict[str, Any] = dict(self.payload)
        merged.update(extra)
        return DomainEvent(
            name=self.name,
            aggregate_id=self.aggregate_id,
            aggregate_type=self.aggregate_type,
            payload=merged,
            occurred_at=self.occurred_at,
            event_id=self.event_id,
        )

    @classmethod
    def from_bus_envelope(cls, payload: Mapping[str, Any]) -> "DomainEvent":
        data = payload.get("data", {})
        return cls(
            name=cast(str, payload["name"]),
            aggregate_id=cast(str, payload["aggregate_id"]),
            aggregate_type=cast(str, payload["aggregate_type"]),
            payload=dict(data) if isinstance(data, Mapping) else {},
            occurred_at=float(payload["occurred_at"]),
            event_id=cast(str, payload["event_id"]),
        )


def envelope_for_bus(evt: DomainEvent) -> MutableMapping[str, Any]:
    return {
        "event_id": evt.event_id,
        "name": evt.name,
        "aggregate_id": evt.aggregate_id,
        "aggregate_type": evt.aggregate_type,
        "occurred_at": evt.occurred_at,
        "data": dict(evt.payload),
    }
