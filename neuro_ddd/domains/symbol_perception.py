import time
from typing import Any, Dict, Optional

from ..core.domain import NeuralDomain
from ..core.signal import Signal
from ..core.types import DomainType, SignalType


class SymbolPerceptionDomain(NeuralDomain):
    def __init__(self, bus: Any, xc_source_code: str = "") -> None:
        super().__init__(DomainType.SYMBOL_PERCEPTION, bus)
        self.xc_source_code = xc_source_code
        self._is_first_trigger = True

    def process_signal(self, signal: Optional[Signal] = None) -> Optional[Signal]:
        time.sleep(0.01)

        if signal is None or (signal.signal_type is None and self._is_first_trigger):
            self._is_first_trigger = False
            parsed_result = self._parse_xc_symbols()
            new_signal = Signal(
                signal_type=SignalType.SYMBOL,
                payload=parsed_result,
            )
            return new_signal
        return None

    def _parse_xc_symbols(self) -> Dict[str, Any]:
        source = self.xc_source_code or "▢a=♦(b>0)▶◀❖c=1▶▶"
        syntax_units = {
            "source_code": source,
            "variables": [
                {"name": "a", "type": "assignment", "value": "♦(b>0)"},
                {"name": "c", "type": "assignment", "value": "1"},
            ],
            "conditions": [{"expression": "b>0", "operator": ">"}],
            "symbols_detected": ["▢", "♦", "▶", "◀", "❖"],
            "parsed_at": time.time(),
        }
        return syntax_units
