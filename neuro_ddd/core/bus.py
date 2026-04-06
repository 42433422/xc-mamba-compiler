import contextvars
import logging
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from .delivery import BroadcastResult, BusHooks, DeliveryErrorPolicy, DeliveryFailure
from .domain import NeuralDomain
from .signal import Signal
from .types import DomainType

logger = logging.getLogger(__name__)

from neuro_ddd.resilience.bus_layer import BusResilience
from neuro_ddd.resilience.circuit_breaker import CircuitOpenError
from neuro_ddd.resilience.rate_limit import RateLimitExceeded

_dispatch_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "neuro_ddd_dispatch_depth", default=0
)


class NeuroBus:
    """Thread-safe neural bus with production delivery controls."""

    def __init__(
        self,
        *,
        delivery_error_policy: DeliveryErrorPolicy = DeliveryErrorPolicy.FAIL_FAST,
        max_dispatch_depth: int = 64,
        hooks: Optional[BusHooks] = None,
        resilience: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self._domains: Dict[DomainType, NeuralDomain] = {}
        self._broadcast_log: List[dict] = []
        self._topic_subscribers: Dict[str, Set[DomainType]] = defaultdict(set)
        self._delivery_error_policy = delivery_error_policy
        self._max_dispatch_depth = max_dispatch_depth
        self._hooks = hooks or BusHooks()
        self._resilience = resilience

    @property
    def delivery_error_policy(self) -> DeliveryErrorPolicy:
        return self._delivery_error_policy

    @delivery_error_policy.setter
    def delivery_error_policy(self, value: DeliveryErrorPolicy) -> None:
        self._delivery_error_policy = value

    def subscribe(self, domain_type: DomainType, event_name: str) -> None:
        with self._lock:
            self._topic_subscribers[event_name].add(domain_type)

    def unsubscribe(self, domain_type: DomainType, event_name: str) -> None:
        with self._lock:
            self._topic_subscribers[event_name].discard(domain_type)

    def subscribers_for(self, event_name: str) -> List[DomainType]:
        with self._lock:
            return list(self._topic_subscribers.get(event_name, ()))

    def register_domain(self, domain: NeuralDomain) -> None:
        dtype = domain.domain_type
        with self._lock:
            if dtype in self._domains:
                raise ValueError(f"Domain {dtype.value} already registered")
            self._domains[dtype] = domain
        logger.info("Domain registered: %s", dtype.value)

    def unregister_domain(self, domain_type: DomainType) -> None:
        with self._lock:
            if domain_type not in self._domains:
                raise KeyError(f"Domain {domain_type.value} not registered")
            del self._domains[domain_type]
        logger.info("Domain unregistered: %s", domain_type.value)

    def _resolve_targets_unlocked(self, signal: Signal) -> List[NeuralDomain]:
        source = signal.source_domain
        if signal.name and self._topic_subscribers.get(signal.name):
            dtypes = self._topic_subscribers[signal.name]
            out: List[NeuralDomain] = []
            for dt in dtypes:
                if dt == source:
                    continue
                dom = self._domains.get(dt)
                if dom is not None:
                    out.append(dom)
                else:
                    logger.warning(
                        "Topic %r: subscriber %s not registered",
                        signal.name,
                        dt.value,
                    )
            return out
        if signal.target_domains:
            out = []
            for dt in signal.target_domains:
                if dt == source:
                    continue
                dom = self._domains.get(dt)
                if dom is not None:
                    out.append(dom)
                else:
                    logger.warning(
                        "Explicit target %s not registered (signal %s)",
                        dt.value,
                        signal.signal_id,
                    )
            return out
        return [d for d in self._domains.values() if d.domain_type != source]

    def _resolve_targets(self, signal: Signal) -> List[NeuralDomain]:
        with self._lock:
            return list(self._resolve_targets_unlocked(signal))

    def _enter_dispatch(self) -> None:
        d = _dispatch_depth.get()
        if d >= self._max_dispatch_depth:
            raise RuntimeError(
                f"Signal dispatch depth exceeded (max_dispatch_depth={self._max_dispatch_depth})"
            )
        _dispatch_depth.set(d + 1)

    def _exit_dispatch(self) -> None:
        d = _dispatch_depth.get()
        if d <= 0:
            _dispatch_depth.set(0)
            return
        _dispatch_depth.set(d - 1)

    def broadcast(
        self,
        signal: Signal,
        *,
        error_policy: Optional[DeliveryErrorPolicy] = None,
    ) -> BroadcastResult:
        policy = error_policy if error_policy is not None else self._delivery_error_policy
        self._enter_dispatch()
        result = BroadcastResult()
        try:
            if self._resilience is not None:
                try:
                    self._resilience.before_broadcast(signal.to_dict())
                except RateLimitExceeded as exc:
                    self._resilience.handle_rate_limit(signal.to_dict(), exc)
                    raise
                except CircuitOpenError:
                    self._resilience.handle_circuit_open(signal.to_dict())
                    if getattr(
                        self._resilience, "on_circuit_open_return_empty", True
                    ):
                        if self._hooks.on_broadcast_end:
                            self._hooks.on_broadcast_end(signal, result)
                        return result
                    raise
            if self._hooks.on_broadcast_begin:
                self._hooks.on_broadcast_begin(signal)
            targets = self._resolve_targets(signal)
            for target in targets:
                try:
                    target.on_receive(signal)
                    result.delivered_domain_types.append(target.domain_type)
                except Exception as exc:
                    failure = DeliveryFailure(
                        domain_type=target.domain_type,
                        signal_id=signal.signal_id,
                        signal_name=signal.name,
                        error=exc,
                    )
                    if self._hooks.on_handler_error:
                        self._hooks.on_handler_error(
                            signal, target.domain_type, exc
                        )
                    if (
                        self._resilience is not None
                        and self._resilience.dead_letter is not None
                    ):
                        self._resilience.dead_letter.push(
                            signal_envelope=signal.to_dict(),
                            reason="handler_error",
                            domain_type=target.domain_type,
                            error=exc,
                        )
                    if policy == DeliveryErrorPolicy.FAIL_FAST:
                        if self._resilience is not None:
                            self._resilience.record_broadcast_failure(exc)
                        logger.exception(
                            "FAIL_FAST: handler error domain=%s signal_id=%s name=%s correlation_id=%s",
                            target.domain_type.value,
                            signal.signal_id,
                            signal.name,
                            signal.correlation_id,
                        )
                        raise
                    logger.exception(
                        "ISOLATE: handler error domain=%s signal_id=%s name=%s correlation_id=%s",
                        target.domain_type.value,
                        signal.signal_id,
                        signal.name,
                        signal.correlation_id,
                    )
                    result.failures.append(failure)
            log_entry = {
                "signal": signal.to_dict(),
                "target_count": len(targets),
                "targets": [d.domain_type.value for d in targets],
                "failure_count": len(result.failures),
            }
            with self._lock:
                self._broadcast_log.append(log_entry)
            if self._resilience is not None:
                if result.ok():
                    self._resilience.record_broadcast_success()
                elif result.failures:
                    self._resilience.record_broadcast_failure(
                        result.failures[0].error
                    )
            if self._hooks.on_broadcast_end:
                self._hooks.on_broadcast_end(signal, result)
            return result
        finally:
            self._exit_dispatch()

    def send_command(self, signal: Signal) -> BroadcastResult:
        if len(signal.target_domains) != 1:
            raise ValueError("send_command requires exactly one target_domains entry")
        return self.broadcast(signal)

    def get_registered_domains(self) -> List[DomainType]:
        with self._lock:
            return list(self._domains.keys())

    def get_broadcast_log(self) -> List[dict]:
        with self._lock:
            return list(self._broadcast_log)

    def __repr__(self) -> str:
        with self._lock:
            registered = [d.value for d in self._domains.keys()]
            n = len(self._broadcast_log)
        return f"NeuroBus(domains={registered}, broadcasts={n})"
