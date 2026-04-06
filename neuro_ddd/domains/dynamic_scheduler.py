import time
from typing import Any, Dict, Optional

from ..core.domain import NeuralDomain
from ..core.signal import Signal
from ..core.types import DomainType, SignalType, SchedulingDecision


class DynamicSchedulerDomain(NeuralDomain):
    def __init__(self, bus: Any, decision_engine: Any = None) -> None:
        super().__init__(DomainType.DYNAMIC_SCHEDULING, bus)
        self.decision_engine = decision_engine
        self.all_signals: Dict[str, Signal] = {}
        self._has_verification_signal = False

    def process_signal(self, signal: Optional[Signal] = None) -> Optional[Signal]:
        if signal is None:
            return None
        time.sleep(0.01)
        signal_key = f"{signal.signal_type.value}_{signal.signal_id}"
        self.all_signals[signal_key] = signal
        if signal.signal_type == SignalType.VERIFICATION:
            self._has_verification_signal = True
        if not self._has_verification_signal:
            return None
        verification_result = self._extract_verification_result()
        if self.decision_engine is None:
            decision = SchedulingDecision.AI_MAIN
            is_fallback = False
        else:
            decision_result = self.decision_engine.make_decision(verification_result)
            decision = decision_result.get("decision", SchedulingDecision.AI_MAIN)
            is_fallback = decision == SchedulingDecision.GCC_FALLBACK
        dispatch_result = self._create_dispatch_payload(decision)
        if is_fallback:
            fb = (
                getattr(self.decision_engine, "fallback_compiler", None)
                if self.decision_engine
                else None
            )
            dispatch_result["fallback_status"] = (
                "engine_configured" if fb is not None else "not_configured"
            )
            dispatch_result["fallback_compiler"] = (
                type(fb).__name__ if fb is not None else None
            )
        new_signal = Signal(
            signal_type=SignalType.DISPATCH,
            payload=dispatch_result,
        )
        return new_signal

    def _extract_verification_result(self) -> str:
        verification_signal = None
        for sig in self.all_signals.values():
            if sig.signal_type == SignalType.VERIFICATION:
                verification_signal = sig
                break
        if verification_signal is None:
            return "异常"
        payload = verification_signal.payload
        if isinstance(payload, dict):
            is_safe = payload.get("is_safe", False)
            mode = payload.get("mode", "normal")
            if is_safe or mode == "normal":
                return "正常"
            else:
                return "异常"
        return "异常"

    def _create_dispatch_payload(self, decision) -> Dict[str, Any]:
        if isinstance(decision, SchedulingDecision):
            decision_value = decision.value
            decision_name = decision.name
        elif isinstance(decision, dict):
            decision_value = decision.get("decision", "unknown")
            decision_name = str(decision_value)
        else:
            decision_value = str(decision)
            decision_name = str(decision)
        payload = {
            "decision": decision_value,
            "decision_type": decision_name,
            "signals_received": len(self.all_signals),
            "signal_types": list(set(s.signal_type.value for s in self.all_signals.values())),
            "dispatched_at": time.time(),
        }
        return payload
