from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from .types import DomainState, DomainType
from .signal import Signal

if TYPE_CHECKING:
    from .bus import NeuroBus


class NeuralDomain(ABC):
    def __init__(self, domain_type: DomainType, bus: "NeuroBus") -> None:
        self.domain_type = domain_type
        self.state = DomainState.IDLE
        self.bus = bus
        bus.register_domain(self)

    @abstractmethod
    def process_signal(self, signal: Signal) -> Optional[Signal]:
        pass

    def on_receive(self, signal: Signal) -> None:
        if self.state != DomainState.IDLE:
            return
        self._transition_to(DomainState.PROCESSING)
        try:
            result = self.process_signal(signal)
            if result is not None:
                self._inherit_trace_if_needed(result, signal)
                self.send_signal(result)
            self._transition_to(DomainState.COMPLETED)
        except Exception:
            self._transition_to(DomainState.ERROR)
            raise
        finally:
            if self.state == DomainState.COMPLETED:
                self._transition_to(DomainState.IDLE)
            elif self.state == DomainState.ERROR:
                self._transition_to(DomainState.IDLE)

    @staticmethod
    def _inherit_trace_if_needed(out: Signal, parent: Signal) -> None:
        if not out.correlation_id and parent.correlation_id:
            out.correlation_id = parent.correlation_id
        if not out.causation_id:
            out.causation_id = parent.signal_id
        if not out.trace_id and getattr(parent, "trace_id", None):
            out.trace_id = parent.trace_id
            if parent.span_id and not out.parent_span_id:
                out.parent_span_id = parent.span_id

    def send_signal(self, signal: Signal) -> None:
        signal.source_domain = self.domain_type
        self.bus.broadcast(signal)

    def _transition_to(self, new_state: DomainState) -> None:
        self.state = new_state

    def __repr__(self) -> str:
        return f"NeuralDomain(type={self.domain_type.value}, state={self.state.value})"
