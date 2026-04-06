"""Lightweight runtime knobs (env-backed for containers / K8s)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


@dataclass(frozen=True)
class NeuroDddConfig:
    """Optional defaults for resilience and observability (no global singleton)."""

    rate_limit_capacity: float = 100.0
    rate_limit_refill_per_s: float = 50.0
    circuit_failure_threshold: int = 5
    circuit_reset_timeout_s: float = 30.0
    dead_letter_max: int = 10_000
    structured_logging: bool = False

    @classmethod
    def from_env(cls) -> "NeuroDddConfig":
        return cls(
            rate_limit_capacity=_env_float("NEURO_DDD_RATE_CAPACITY", 100.0),
            rate_limit_refill_per_s=_env_float("NEURO_DDD_RATE_REFILL", 50.0),
            circuit_failure_threshold=int(
                os.environ.get("NEURO_DDD_CB_FAILURES", "5") or "5"
            ),
            circuit_reset_timeout_s=_env_float("NEURO_DDD_CB_RESET_S", 30.0),
            dead_letter_max=int(os.environ.get("NEURO_DDD_DLQ_MAX", "10000") or "10000"),
            structured_logging=_env_bool("NEURO_DDD_JSON_LOG", False),
        )
