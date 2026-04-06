import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .types import SignalType, DomainType


@dataclass(slots=True)
class Signal:
    """Neural message. For DDD-style use, set ``name`` for semantic routing (topic)."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    signal_type: Optional[SignalType] = None
    source_domain: Optional[DomainType] = None
    target_domains: List[DomainType] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    name: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    def to_dict(self) -> dict:
        td = self.target_domains
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value if self.signal_type else None,
            "source_domain": self.source_domain.value if self.source_domain else None,
            "target_domains": [d.value for d in td],
            "payload": self.payload,
            "timestamp": self.timestamp,
            "name": self.name,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        st_raw = data.get("signal_type")
        signal_type = SignalType(st_raw) if st_raw is not None else None
        src_raw = data.get("source_domain")
        source_domain = DomainType(src_raw) if src_raw is not None else None
        targets = [
            DomainType(x) for x in (data.get("target_domains") or []) if x is not None
        ]
        return cls(
            signal_id=str(data.get("signal_id") or uuid.uuid4().hex[:8]),
            signal_type=signal_type,
            source_domain=source_domain,
            target_domains=targets,
            payload=dict(data.get("payload") or {}),
            timestamp=float(data.get("timestamp") or time.time()),
            name=data.get("name"),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
            parent_span_id=data.get("parent_span_id"),
        )

    def derive(
        self,
        *,
        name: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        payload: Optional[Dict[str, Any]] = None,
        target_domains: Optional[List[DomainType]] = None,
    ) -> "Signal":
        """New signal (new ``signal_id``) for follow-up broadcasts: keeps correlation/trace, sets causation."""
        return Signal(
            signal_type=self.signal_type if signal_type is None else signal_type,
            source_domain=None,
            target_domains=[] if target_domains is None else list(target_domains),
            payload=dict(self.payload) if payload is None else dict(payload),
            name=self.name if name is None else name,
            correlation_id=self.correlation_id,
            causation_id=self.signal_id,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.span_id,
        )

    def __repr__(self) -> str:
        return (
            f"Signal(id={self.signal_id}, type={self.signal_type}, name={self.name!r}, "
            f"source={self.source_domain}, targets={[d.value for d in self.target_domains]})"
        )
