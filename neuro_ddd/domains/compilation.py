import time
from typing import Any, Dict, Optional

from ..core.domain import NeuralDomain
from ..core.signal import Signal
from ..core.types import DomainType, SignalType


class CompilationDomain(NeuralDomain):
    def __init__(self, bus: Any) -> None:
        super().__init__(DomainType.COMPILATION, bus)

    def process_signal(self, signal: Optional[Signal] = None) -> Optional[Signal]:
        if signal is None or signal.signal_type != SignalType.SYMBOL:
            return None
        time.sleep(0.01)
        assembly_result = self._generate_riscv_assembly(signal.payload)
        new_signal = Signal(
            signal_type=SignalType.ASSEMBLY,
            payload=assembly_result,
        )
        return new_signal

    def _generate_riscv_assembly(self, symbol_payload: Dict[str, Any]) -> Dict[str, Any]:
        variables = symbol_payload.get("variables", [])
        instructions = []
        for var in variables:
            var_name = var.get("name", "")
            var_value = var.get("value", "")
            instructions.append({
                "operation": "li",
                "operands": [f"reg_{var_name}", var_value],
                "comment": f"Load {var_name}",
            })
        conditions = symbol_payload.get("conditions", [])
        for cond in conditions:
            expr = cond.get("expression", "")
            op = cond.get("operator", ">")
            instructions.append({
                "operation": "blt",
                "operands": ["b", "0", ".L_else"],
                "comment": f"Branch if {expr}",
            })
        assembly_output = {
            "architecture": "RISC-V",
            "model": "Mamba-Small",
            "instructions": instructions,
            "generated_at": time.time(),
        }
        return assembly_output
