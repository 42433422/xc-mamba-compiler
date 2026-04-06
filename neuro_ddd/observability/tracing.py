"""Trace identifiers on ``Signal`` + structured logging / optional OpenTelemetry span."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Dict, Optional

from neuro_ddd.core.delivery import BroadcastResult
from neuro_ddd.core.signal import Signal


def _hex(nbytes: int) -> str:
    return secrets.token_hex(nbytes)


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None

    @classmethod
    def root(cls) -> "TraceContext":
        return cls(trace_id=_hex(16), span_id=_hex(8), parent_span_id=None)

    def child_span(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            span_id=_hex(8),
            parent_span_id=self.span_id,
        )


def attach_trace_to_signal(signal: Signal, trace: Optional[TraceContext] = None) -> Signal:
    """Mutates ``signal`` trace fields; sets ``correlation_id`` from trace if missing."""
    t = trace or TraceContext.root()
    signal.trace_id = t.trace_id
    signal.span_id = t.span_id
    signal.parent_span_id = t.parent_span_id
    if not signal.correlation_id:
        signal.correlation_id = t.trace_id
    return signal


def new_root_trace() -> TraceContext:
    return TraceContext.root()


def structured_log_extra(signal: Signal) -> Dict[str, Any]:
    """Use with ``logging.Logger.*(..., extra=structured_log_extra(sig))`` and a JSON formatter."""
    return {
        "neuro_signal_id": signal.signal_id,
        "neuro_signal_name": signal.name,
        "correlation_id": signal.correlation_id,
        "causation_id": signal.causation_id,
        "trace_id": getattr(signal, "trace_id", None),
        "span_id": getattr(signal, "span_id", None),
        "parent_span_id": getattr(signal, "parent_span_id", None),
    }


def broadcast_result_extra(signal: Signal, result: BroadcastResult) -> Dict[str, Any]:
    """Structured fields for a completed broadcast (resolved targets, per-domain attempts, failures)."""
    return {
        **structured_log_extra(signal),
        "neuro_resolved_targets": [d.value for d in result.resolved_domain_types],
        "neuro_delivered": [d.value for d in result.delivered_domain_types],
        "neuro_failure_domains": [f.domain_type.value for f in result.failures],
        "neuro_failure_count": len(result.failures),
        "neuro_partial_success": result.partial_success(),
        "neuro_attempts": [
            {
                "domain": a.domain_type.value,
                "status": a.status.value,
                "duration_ms": round(a.duration_ms, 6),
                "error": type(a.error).__name__ if a.error else None,
            }
            for a in result.attempts
        ],
    }


class _NoopCtx:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *a: Any) -> None:
        return None


def try_start_otel_span(signal: Signal, span_name: str) -> Any:
    """If ``opentelemetry`` is installed, start a span; otherwise return a no-op context manager."""
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("neuro_ddd")
        return tracer.start_as_current_span(
            span_name,
            attributes={
                "neuro.signal_id": signal.signal_id,
                "neuro.signal_name": signal.name or "",
                "neuro.correlation_id": signal.correlation_id or "",
                "neuro.trace_id": signal.trace_id or "",
                "neuro.span_id": signal.span_id or "",
            },
        )
    except Exception:
        return _NoopCtx()
