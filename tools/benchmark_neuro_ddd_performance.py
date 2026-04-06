#!/usr/bin/env python3
"""
Neuro-DDD 可复现性能对比（本仓库根目录运行）

对比维度（方法论见 README「性能基准」）：
1. AsyncNeuroBus + asyncio.gather 并行投递 vs 同步串行 for-loop（模拟传统分层里顺序调用）
2. 简单 CRUD：直接方法调用 vs 经 SoftwareDomain.on_receive（不经总线广播）
3. 同步 neuro_ddd.NeuroBus：相对「手写 for 循环调用 on_receive」的调度开销

输出：reports/neuro_ddd_benchmark.json

默认参数（贴近业务，非微基准噪声）：
- 轻 I/O：每域 ~18ms，模拟跨服务/缓存未命中级延迟；并行相对串行应有明显收益。
- 重 I/O：每域 ~120ms，模拟外部 API / 推理子步骤级延迟。
- 域数量默认 4，接近符号→编译→安全→调度流水线深度。
- 快速冒烟：``python tools/benchmark_neuro_ddd_performance.py --quick``
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class ScenarioStats:
    name: str
    iterations: int
    avg_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    throughput_ops_s: float
    notes: str = ""


def _stats(name: str, latencies_ms: List[float], iterations: int, notes: str = "") -> ScenarioStats:
    if not latencies_ms:
        return ScenarioStats(name, iterations, 0.0, 0.0, 0.0, 0.0, 0.0, notes)
    total_s = sum(latencies_ms) / 1000.0
    thr = iterations / total_s if total_s > 0 else 0.0
    return ScenarioStats(
        name=name,
        iterations=iterations,
        avg_ms=statistics.mean(latencies_ms),
        median_ms=statistics.median(latencies_ms),
        min_ms=min(latencies_ms),
        max_ms=max(latencies_ms),
        throughput_ops_s=thr,
        notes=notes,
    )


def bench_traditional_sequential(iterations: int, delay_ms: float, n_handlers: int) -> ScenarioStats:
    """同步串行：同一线程内顺序 sleep，模拟传统服务链."""

    class Handler:
        def __init__(self, delay_s: float) -> None:
            self._d = delay_s

        def process(self, _data: Any) -> str:
            time.sleep(self._d)
            return "ok"

    delay_s = delay_ms / 1000.0
    handlers = [Handler(delay_s) for _ in range(n_handlers)]
    lat: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        for h in handlers:
            h.process({})
        lat.append((time.perf_counter() - t0) * 1000)
    return _stats(
        "traditional_sequential_sync",
        lat,
        iterations,
        notes=f"{n_handlers} handlers, sleep({delay_ms}ms) each, same thread",
    )


async def bench_async_parallel_bus(
    iterations: int, delay_ms: float, n_domains: int
) -> ScenarioStats:
    from neuro_ddd_software import NeuroSignal, ProcessingResult, SoftwareDomain
    from neuro_ddd_software.core.async_bus import AsyncNeuroBus

    class ParallelDomain(SoftwareDomain):
        def __init__(self, name: str) -> None:
            super().__init__(name)
            self._delay = delay_ms / 1000.0

        async def async_process_signal(self, signal, context):  # type: ignore[override]
            await asyncio.sleep(self._delay)
            return ProcessingResult(success=True, result_data=self.domain_name)

    lat: List[float] = []
    async with AsyncNeuroBus() as bus:
        domains = [ParallelDomain(f"d{i}") for i in range(n_domains)]
        for d in domains:
            await d.set_bus(bus)
            bus.subscribe(d.domain_name, ["parallel_bench"], d.on_receive)

        for _ in range(iterations):
            sig = NeuroSignal(
                signal_type="parallel_bench",
                source_domain="benchmark",
                target_domains=[d.domain_name for d in domains],
                payload={},
            )
            t0 = time.perf_counter()
            await bus.broadcast(sig, wait_for_results=True)
            lat.append((time.perf_counter() - t0) * 1000)

    return _stats(
        "async_neuro_bus_parallel",
        lat,
        iterations,
        notes=f"{n_domains} domains, asyncio.gather in broadcast, sleep({delay_ms}ms) each",
    )


def bench_traditional_crud(iterations: int) -> ScenarioStats:
    class Repository:
        def __init__(self) -> None:
            self._cache: Dict[str, str] = {}

        def save(self, k: str, v: str) -> None:
            self._cache[k] = v

        def get(self, k: str) -> Optional[str]:
            return self._cache.get(k)

    class Service:
        def __init__(self) -> None:
            self.repo = Repository()

        def set_value(self, k: str, v: str) -> None:
            self.repo.save(k, v)

        def get_value(self, k: str) -> Optional[str]:
            return self.repo.get(k)

    svc = Service()
    lat: List[float] = []
    for i in range(iterations):
        t0 = time.perf_counter()
        svc.set_value(f"k{i}", f"v{i}")
        svc.get_value(f"k{i}")
        lat.append((time.perf_counter() - t0) * 1000)
    return _stats("traditional_crud_sync", lat, iterations, notes="direct service + repo")


async def bench_neuro_crud_domain_only(iterations: int) -> ScenarioStats:
    """经 SoftwareDomain 处理路径（与对照组同等工作量，不经总线）。"""
    from neuro_ddd_software import NeuroSignal, ProcessingResult, SoftwareDomain

    class CRUDDomain(SoftwareDomain):
        def __init__(self) -> None:
            super().__init__("crud_bench")
            self._cache: Dict[str, str] = {}

        async def async_process_signal(self, signal, context):  # type: ignore[override]
            key = signal.payload.get("key")
            action = signal.payload.get("action")
            if action == "set":
                self._cache[key] = signal.payload.get("value", "")
                return ProcessingResult(success=True)
            if action == "get":
                return ProcessingResult(success=True, result_data=self._cache.get(key))
            return ProcessingResult(success=False, error="unknown")

    dom = CRUDDomain()
    lat: List[float] = []
    for i in range(iterations):
        t0 = time.perf_counter()
        await dom.on_receive(
            NeuroSignal(
                signal_type="crud",
                source_domain="bench",
                payload={"action": "set", "key": f"k{i}", "value": f"v{i}"},
            )
        )
        await dom.on_receive(
            NeuroSignal(
                signal_type="crud",
                source_domain="bench",
                payload={"action": "get", "key": f"k{i}"},
            )
        )
        lat.append((time.perf_counter() - t0) * 1000)
    return _stats(
        "neuro_software_domain_on_receive_only",
        lat,
        iterations,
        notes="SoftwareDomain.on_receive x2 per iter, no bus.broadcast",
    )


def bench_neuro_ddd_sync_bus_overhead(iterations: int, n_domains: int) -> Dict[str, Any]:
    from neuro_ddd.core.bus import NeuroBus
    from neuro_ddd.core.delivery import DeliveryErrorPolicy
    from neuro_ddd.core.domain import NeuralDomain
    from neuro_ddd.core.signal import Signal
    from neuro_ddd.core.types import DomainType

    class Spy(NeuralDomain):
        def __init__(self, bus: NeuroBus, dtype: DomainType) -> None:
            super().__init__(dtype, bus)

        def process_signal(self, signal):  # type: ignore[no-untyped-def]
            return None

    pipeline = (
        DomainType.SYMBOL_PERCEPTION,
        DomainType.COMPILATION,
        DomainType.SECURITY_VERIFICATION,
        DomainType.DYNAMIC_SCHEDULING,
    )
    n = max(1, min(n_domains, len(pipeline)))
    types = pipeline[:n]

    lat_bus: List[float] = []
    bus = NeuroBus(
        delivery_error_policy=DeliveryErrorPolicy.ISOLATE,
        record_broadcasts=False,
    )
    spies = [Spy(bus, t) for t in types]
    sig = Signal(payload={"bench": True})
    for _ in range(iterations):
        t0 = time.perf_counter()
        bus.broadcast(sig)
        lat_bus.append((time.perf_counter() - t0) * 1000)

    lat_direct: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        for s in spies:
            s.on_receive(sig)
        lat_direct.append((time.perf_counter() - t0) * 1000)

    s_bus = _stats(
        f"neuro_ddd_sync_bus_{n}_domains",
        lat_bus,
        iterations,
        notes=(
            f"NeuroBus.broadcast to {n}x on_receive (record_broadcasts=False)"
        ),
    )
    s_dir = _stats(
        f"neuro_ddd_direct_loop_{n}_domains",
        lat_direct,
        iterations,
        notes=f"for-loop on_receive x{n}",
    )
    ratio = (s_bus.avg_ms / s_dir.avg_ms) if s_dir.avg_ms > 0 else None
    if ratio is not None:
        s_bus.notes += f" | overhead_vs_direct_loop={ratio:.2f}x avg latency"
    return {
        "bus": scenario_to_dict(s_bus),
        "direct_loop": scenario_to_dict(s_dir),
        "avg_latency_ratio_bus_over_direct": round(ratio, 4) if ratio else None,
    }


def scenario_to_dict(s: ScenarioStats) -> Dict[str, Any]:
    d = asdict(s)
    return d


async def _parallel_pair(
    iterations: int, delay_ms: float, n_handlers: int
) -> Dict[str, Any]:
    seq = bench_traditional_sequential(iterations, delay_ms, n_handlers)
    par = await bench_async_parallel_bus(iterations, delay_ms, n_handlers)
    ratio = (
        (seq.median_ms / par.median_ms) if par.median_ms and par.median_ms > 0 else None
    )
    return {
        "delay_ms_per_handler": delay_ms,
        "iterations": iterations,
        "traditional_sequential_sync": scenario_to_dict(seq),
        "async_neuro_bus_parallel": scenario_to_dict(par),
        "sequential_median_ms_over_parallel_median_ms": round(ratio, 4)
        if ratio is not None
        else None,
    }


async def run_all(
    parallel_iters: int,
    parallel_iters_heavy: int,
    crud_iters: int,
    delay_ms_micro: float,
    delay_ms_heavy: float,
    n_handlers: int,
    sync_bus_iters: int,
    profile: str,
) -> Dict[str, Any]:
    wall0 = time.perf_counter()
    pair_micro = await _parallel_pair(parallel_iters, delay_ms_micro, n_handlers)
    pair_heavy = await _parallel_pair(parallel_iters_heavy, delay_ms_heavy, n_handlers)
    trad_crud = bench_traditional_crud(crud_iters)
    neuro_crud = await bench_neuro_crud_domain_only(crud_iters)
    sync_bus = bench_neuro_ddd_sync_bus_overhead(sync_bus_iters, n_handlers)

    return {
        "generated_at_unix": time.time(),
        "wall_clock_total_s": round(time.perf_counter() - wall0, 3),
        "python": sys.version.split()[0],
        "parameters": {
            "profile": profile,
            "parallel_iterations_light_io": parallel_iters,
            "parallel_iterations_heavy_io": parallel_iters_heavy,
            "crud_iterations": crud_iters,
            "delay_ms_light_io": delay_ms_micro,
            "delay_ms_heavy_io": delay_ms_heavy,
            "handler_or_domain_count": n_handlers,
            "sync_bus_iterations": sync_bus_iters,
            "delay_semantics_zh": (
                "light_io≈跨服务/Redis 量级；heavy_io≈外部 API 或推理子步骤量级；"
                "二者均用 sleep 模拟等待，非 CPU 密集。"
            ),
        },
        "scenarios": {
            "parallel_light_io": pair_micro,
            "parallel_heavy_io": pair_heavy,
            "parallel_interpretation": (
                "With tiny per-handler delays, asyncio framework cost can dominate; "
                "with larger I/O-like delays, wall-clock approaches max(delay) instead of sum(delay)."
            ),
            "crud": {
                "traditional": scenario_to_dict(trad_crud),
                "neuro_domain_path": scenario_to_dict(neuro_crud),
            },
            "sync_neuro_ddd_bus": sync_bus,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "默认可复现「业务向」延迟与域数；--quick 为原玩具参数（秒级跑完）。"
        )
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="快速冒烟：小迭代、2ms/12ms 延迟、3 域（易放大框架噪声，仅作对比）",
    )
    p.add_argument(
        "--parallel-iters",
        type=int,
        default=100,
        help="轻 I/O 场景每轮迭代次数（默认 100）",
    )
    p.add_argument(
        "--parallel-iters-heavy",
        type=int,
        default=30,
        help="重 I/O 场景每轮迭代次数（默认 30，避免串行 4×delay 过长）",
    )
    p.add_argument(
        "--crud-iters",
        type=int,
        default=2000,
        help="CRUD 对照迭代次数（默认 2000）",
    )
    p.add_argument(
        "--delay-ms-light",
        type=float,
        default=18.0,
        dest="delay_ms_micro",
        help="轻 I/O：每域 sleep 毫秒，模拟跨服务/缓存（默认 18）",
    )
    p.add_argument(
        "--delay-ms-heavy",
        type=float,
        default=120.0,
        help="重 I/O：每域 sleep 毫秒，模拟 API/推理片（默认 120）",
    )
    p.add_argument(
        "--handlers",
        type=int,
        default=4,
        help="并行场景域数量（默认 4，贴近多域流水线）",
    )
    p.add_argument(
        "--sync-bus-iters",
        type=int,
        default=8000,
        help="同步 NeuroBus vs 裸循环采样次数（默认 8000）",
    )
    args = p.parse_args()

    if args.quick:
        profile = "quick_smoke"
        parallel_iters = 60
        parallel_iters_heavy = 40
        crud_iters = 500
        delay_micro = 2.0
        delay_heavy = 12.0
        n_handlers = 3
        sync_bus_iters = min(5000, max(500, crud_iters * 5))
    else:
        profile = "business_default"
        parallel_iters = args.parallel_iters
        parallel_iters_heavy = args.parallel_iters_heavy
        crud_iters = args.crud_iters
        delay_micro = args.delay_ms_micro
        delay_heavy = args.delay_ms_heavy
        n_handlers = args.handlers
        sync_bus_iters = args.sync_bus_iters

    report = asyncio.run(
        run_all(
            parallel_iters,
            parallel_iters_heavy,
            crud_iters,
            delay_micro,
            delay_heavy,
            n_handlers,
            sync_bus_iters,
            profile,
        )
    )
    out_dir = REPO_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "neuro_ddd_benchmark.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
