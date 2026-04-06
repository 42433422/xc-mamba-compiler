from enum import Enum, auto


class SignalType(Enum):
    SYMBOL = "S"
    ASSEMBLY = "B"
    VERIFICATION = "J"
    DISPATCH = "D"


class DomainType(Enum):
    SYMBOL_PERCEPTION = "symbol_perception"
    COMPILATION = "compilation"
    SECURITY_VERIFICATION = "security_verification"
    DYNAMIC_SCHEDULING = "dynamic_scheduling"


class SchedulingDecision(Enum):
    AI_MAIN = "AI主路编译"
    GCC_FALLBACK = "GCC兜底编译"


class DomainState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
