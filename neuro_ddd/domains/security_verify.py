import time
from typing import Any, Dict, List, Optional

from ..core.domain import NeuralDomain
from ..core.signal import Signal
from ..core.types import DomainType, SignalType


class SecurityVerificationDomain(NeuralDomain):
    def __init__(self, bus: Any, mode: str = "normal") -> None:
        super().__init__(DomainType.SECURITY_VERIFICATION, bus)
        self.mode = mode
        self.received_signals: List[Signal] = []
        self._has_symbol_signal = False
        self._has_assembly_signal = False

    def process_signal(self, signal: Optional[Signal] = None) -> Optional[Signal]:
        if signal is None:
            return None
        if signal.signal_type not in (SignalType.SYMBOL, SignalType.ASSEMBLY):
            return None
        time.sleep(0.01)
        self.received_signals.append(signal)
        if signal.signal_type == SignalType.SYMBOL:
            self._has_symbol_signal = True
        elif signal.signal_type == SignalType.ASSEMBLY:
            self._has_assembly_signal = True
        if self._has_symbol_signal and self._has_assembly_signal:
            verification_result = self._execute_verification()
            new_signal = Signal(
                signal_type=SignalType.VERIFICATION,
                payload=verification_result,
            )
            return new_signal
        return None

    def _execute_verification(self) -> Dict[str, Any]:
        is_safe = self.mode == "normal"
        result = {
            "mode": self.mode,
            "is_safe": is_safe,
            "status": "passed" if is_safe else "failed",
            "checked_signals": len(self.received_signals),
            "verified_at": time.time(),
        }
        return result
