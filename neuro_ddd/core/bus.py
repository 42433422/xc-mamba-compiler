import contextlib
import contextvars
import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from neuro_ddd.resilience.circuit_breaker import CircuitOpenError
from neuro_ddd.resilience.rate_limit import RateLimitExceeded

from .delivery import (
    BroadcastLoopGuardTriggered,
    BroadcastResult,
    BroadcastTargetLimitExceeded,
    BusHooks,
    DeliveryErrorPolicy,
    DeliveryFailure,
    DomainDeliveryRecord,
    DomainDeliveryStatus,
)
from .domain import NeuralDomain
from .signal import Signal
from .types import DomainType

logger = logging.getLogger(__name__)

_dispatch_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "neuro_ddd_dispatch_depth", default=0
)

_fingerprint_chain: contextvars.ContextVar[tuple[tuple[str, str], ...]] = (
    contextvars.ContextVar("neuro_ddd_fingerprint_chain", default=())
)


def _signal_fingerprint(signal: Signal) -> tuple[str, str]:
    topic = (
        signal.name
        or (signal.signal_type.value if signal.signal_type is not None else "")
        or "*"
    )
    corr = signal.correlation_id or signal.signal_id or ""
    return (topic, corr)


class NeuroBus:
    """Thread-safe neural bus with delivery policies, tracing-friendly results, and safety rails.

    * ``BroadcastResult`` records resolved targets, per-domain attempts (latency, ok/fail), and
      ``partial_success()`` for ISOLATE + mixed outcomes. Use ``BusHooks.on_partial_failure`` to
      trigger compensations / sagas.
    * ``loop_guard_max_same_fingerprint``: cap nested broadcasts sharing the same (topic,
      correlation) fingerprint (``None`` disables). Complements ``max_dispatch_depth``.
    * ``max_targets_per_broadcast``: hard cap on resolved handler count (storm guard).
    * ``serialize_broadcasts``: global re-entrant lock so only one top-level broadcast runs at a
      time (reduces in-process races on shared mutable state; has a throughput cost).
    * Set logger ``neuro_ddd.core.bus`` to DEBUG for structured ``broadcast_result_extra`` on each
      completed broadcast.
    """

    def __init__(
        self,
        *,
        delivery_error_policy: DeliveryErrorPolicy = DeliveryErrorPolicy.FAIL_FAST,
        max_dispatch_depth: int = 64,
        hooks: Optional[BusHooks] = None,
        resilience: Any = None,
        record_broadcasts: bool = True,
        loop_guard_max_same_fingerprint: Optional[int] = 4,
        max_targets_per_broadcast: Optional[int] = None,
        serialize_broadcasts: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self._domains: Dict[DomainType, NeuralDomain] = {}
        self._broadcast_log: List[dict] = []
        self._topic_subscribers: Dict[str, Set[DomainType]] = defaultdict(set)
        self._delivery_error_policy = delivery_error_policy
        self._max_dispatch_depth = max_dispatch_depth
        self._hooks = hooks or BusHooks()
        self._resilience = resilience
        self._record_broadcasts = record_broadcasts
        self._loop_guard_max = loop_guard_max_same_fingerprint
        self._max_targets = max_targets_per_broadcast
        self._serialize_broadcasts = serialize_broadcasts
        self._broadcast_serial = threading.RLock()

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
        try:
            cm = self._broadcast_serial if self._serialize_broadcasts else contextlib.nullcontext()
            with cm:
                return self._broadcast_unlocked(signal, policy)
        finally:
            self._exit_dispatch()

    def _broadcast_unlocked(
        self,
        signal: Signal,
        policy: DeliveryErrorPolicy,
    ) -> BroadcastResult:
        result = BroadcastResult()
        hooks = self._hooks
        res = self._resilience
        need_env = res is not None or self._record_broadcasts
        env: Optional[dict] = signal.to_dict() if need_env else None
        chain_pushed = False
        if res is not None:
            assert env is not None
            try:
                res.before_broadcast(env)
            except RateLimitExceeded as exc:
                res.handle_rate_limit(env, exc)
                raise
            except CircuitOpenError:
                res.handle_circuit_open(env)
                if getattr(res, "on_circuit_open_return_empty", True):
                    if hooks.on_broadcast_end:
                        hooks.on_broadcast_end(signal, result)
                    return result
                raise
        if hooks.on_broadcast_begin:
            hooks.on_broadcast_begin(signal)
        targets = self._resolve_targets(signal)
        result.resolved_domain_types = [t.domain_type for t in targets]

        if self._max_targets is not None and len(targets) > self._max_targets:
            raise BroadcastTargetLimitExceeded(self._max_targets, len(targets))

        if self._loop_guard_max is not None:
            fp = _signal_fingerprint(signal)
            chain = _fingerprint_chain.get()
            if chain.count(fp) >= self._loop_guard_max:
                raise BroadcastLoopGuardTriggered(fp, self._loop_guard_max)
            _fingerprint_chain.set(chain + (fp,))
            chain_pushed = True

        try:
            _log_exc = logger.isEnabledFor(logging.ERROR)
            _log_trace = logger.isEnabledFor(logging.DEBUG)
            for target in targets:
                t0 = time.perf_counter()
                try:
                    target.on_receive(signal)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    result.delivered_domain_types.append(target.domain_type)
                    result.attempts.append(
                        DomainDeliveryRecord(
                            domain_type=target.domain_type,
                            status=DomainDeliveryStatus.OK,
                            duration_ms=elapsed_ms,
                        )
                    )
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    failure = DeliveryFailure(
                        domain_type=target.domain_type,
                        signal_id=signal.signal_id,
                        signal_name=signal.name,
                        error=exc,
                        duration_ms=elapsed_ms,
                    )
                    result.attempts.append(
                        DomainDeliveryRecord(
                            domain_type=target.domain_type,
                            status=DomainDeliveryStatus.FAILED,
                            duration_ms=elapsed_ms,
                            error=exc,
                        )
                    )
                    if hooks.on_handler_error:
                        hooks.on_handler_error(signal, target.domain_type, exc)
                    if res is not None and res.dead_letter is not None:
                        res.dead_letter.push(
                            signal_envelope=env if env is not None else signal.to_dict(),
                            reason="handler_error",
                            domain_type=target.domain_type,
                            error=exc,
                        )
                    if policy == DeliveryErrorPolicy.FAIL_FAST:
                        if res is not None:
                            res.record_broadcast_failure(exc)
                        if _log_exc:
                            logger.exception(
                                "FAIL_FAST: handler error domain=%s signal_id=%s name=%s correlation_id=%s",
                                target.domain_type.value,
                                signal.signal_id,
                                signal.name,
                                signal.correlation_id,
                            )
                        raise
                    if _log_exc:
                        logger.exception(
                            "ISOLATE: handler error domain=%s signal_id=%s name=%s correlation_id=%s",
                            target.domain_type.value,
                            signal.signal_id,
                            signal.name,
                            signal.correlation_id,
                        )
                    result.failures.append(failure)
            if self._record_broadcasts:
                assert env is not None
                log_entry = {
                    "signal": env,
                    "target_count": len(targets),
                    "targets": [d.domain_type.value for d in targets],
                    "failure_count": len(result.failures),
                    "attempts": [
                        {
                            "domain": a.domain_type.value,
                            "status": a.status.value,
                            "duration_ms": a.duration_ms,
                            "error": type(a.error).__name__ if a.error else None,
                        }
                        for a in result.attempts
                    ],
                }
                with self._lock:
                    self._broadcast_log.append(log_entry)
            if res is not None:
                if result.ok():
                    res.record_broadcast_success()
                elif result.failures:
                    res.record_broadcast_failure(result.failures[0].error)
            if (
                hooks.on_partial_failure
                and policy == DeliveryErrorPolicy.ISOLATE
                and result.partial_success()
            ):
                hooks.on_partial_failure(signal, result)
            if hooks.on_broadcast_end:
                hooks.on_broadcast_end(signal, result)
            if _log_trace:
                try:
                    from neuro_ddd.observability.tracing import broadcast_result_extra

                    logger.debug(
                        "broadcast_done targets=%d delivered=%d failures=%d",
                        len(result.resolved_domain_types),
                        len(result.delivered_domain_types),
                        len(result.failures),
                        extra=broadcast_result_extra(signal, result),
                    )
                except Exception:
                    logger.debug("broadcast_done (trace extra skipped)", exc_info=True)
            return result
        finally:
            if chain_pushed:
                chain = _fingerprint_chain.get()
                if chain:
                    _fingerprint_chain.set(chain[:-1])

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
