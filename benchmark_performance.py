"""
Neuro-DDD vs 传统DDD 真实性能基准测试
=====================================
测试场景：
1. 简单CRUD操作（潜意识加速场景）
2. 复杂业务逻辑（显意识处理场景）
3. 高并发请求（并行处理优势）
4. 错误处理性能（熔断器效果）
5. 信号广播 vs 方法调用

每个测试运行 1000 次，统计平均延迟、P95、P99、吞吐量
"""

import asyncio
import time
import statistics
from typing import List, Dict
import sys

sys.path.insert(0, 'e:/X语音')


class BenchmarkResult:
    """基准测试结果"""
    def __init__(self, name: str):
        self.name = name
        self.latencies_ms: List[float] = []
        self.start_time = 0
        self.end_time = 0
    
    def add_latency(self, latency_ms: float):
        self.latencies_ms.append(latency_ms)
    
    def calculate_stats(self) -> Dict:
        if not self.latencies_ms:
            return {}
        
        sorted_latencies = sorted(self.latencies_ms)
        n = len(sorted_latencies)
        
        return {
            "name": self.name,
            "count": n,
            "total_time_s": self.end_time - self.start_time,
            "avg_ms": statistics.mean(self.latencies_ms),
            "median_ms": statistics.median(self.latencies_ms),
            "p95_ms": sorted_latencies[int(n * 0.95)] if n > 20 else sorted_latencies[-1],
            "p99_ms": sorted_latencies[int(n * 0.99)] if n > 100 else sorted_latencies[-1],
            "min_ms": min(self.latencies_ms),
            "max_ms": max(self.latencies_ms),
            "stddev_ms": statistics.stdev(self.latencies_ms) if n > 1 else 0,
            "throughput_ops": n / (self.end_time - self.start_time) if (self.end_time - self.start_time) > 0 else 0,
        }


async def benchmark_neuro_crud(iterations: int = 1000) -> BenchmarkResult:
    """测试1: Neuro-DDD简单CRUD（潜意识处理）"""
    from neuro_ddd_software import (
        NeuroSignal, AsyncNeuroBus, SoftwareDomain,
        ProcessingMode, ProcessingContext, ProcessingResult
    )
    
    result = BenchmarkResult("Neuro-DDD CRUD (Subconscious)")
    
    class CRUDDomain(SoftwareDomain):
        def __init__(self):
            super().__init__("crud_domain", default_mode=ProcessingMode.SUBCONSCIOUS)
            self._cache = {}
        
        async def async_process_signal(self, signal, context):
            key = signal.payload.get("key")
            action = signal.payload.get("action")
            
            if action == "get":
                return ProcessingResult(
                    success=True,
                    result_data=self._cache.get(key),
                    metadata={"cached": key in self._cache}
                )
            elif action == "set":
                self._cache[key] = signal.payload.get("value")
                return ProcessingResult(success=True)
            elif action == "delete":
                self._cache.pop(key, None)
                return ProcessingResult(success=True)
            
            return ProcessingResult(success=False, error="Unknown action")
    
    async with AsyncNeuroBus() as bus:
        domain = CRUDDomain()
        await domain.set_bus(bus)
        
        result.start_time = time.time()
        
        for i in range(iterations):
            # SET
            set_signal = NeuroSignal.create_request(
                source="benchmark",
                signal_type="crud_operation",
                payload={"action": "set", "key": f"key_{i}", "value": f"value_{i}"}
            )
            start = time.perf_counter()
            await domain.on_receive(set_signal)
            set_latency = (time.perf_counter() - start) * 1000
            
            # GET
            get_signal = NeuroSignal.create_request(
                source="benchmark",
                signal_type="crud_operation",
                payload={"action": "get", "key": f"key_{i}"}
            )
            start = time.perf_counter()
            await domain.on_receive(get_signal)
            get_latency = (time.perf_counter() - start) * 1000
            
            result.add_latency(set_latency)
            result.add_latency(get_latency)
        
        result.end_time = time.time()
    
    return result


async def benchmark_traditional_crud(iterations: int = 1000) -> BenchmarkResult:
    """测试1 对照：传统DDD风格CRUD"""
    result = BenchmarkResult("Traditional DDD CRUD")
    
    class TraditionalRepository:
        def __init__(self):
            self._cache = {}
        
        def save(self, key, value):
            self._cache[key] = value
        
        def get(self, key):
            return self._cache.get(key)
        
        def delete(self, key):
            self._cache.pop(key, None)
    
    class TraditionalService:
        def __init__(self):
            self.repo = TraditionalRepository()
        
        def set_value(self, key, value):
            self.repo.save(key, value)
        
        def get_value(self, key):
            return self.repo.get(key)
    
    service = TraditionalService()
    result.start_time = time.time()
    
    for i in range(iterations):
        start = time.perf_counter()
        service.set_value(f"key_{i}", f"value_{i}")
        set_latency = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        service.get_value(f"key_{i}")
        get_latency = (time.perf_counter() - start) * 1000
        
        result.add_latency(set_latency)
        result.add_latency(get_latency)
    
    result.end_time = time.time()
    return result


async def benchmark_neuro_parallel(iterations: int = 100) -> BenchmarkResult:
    """测试2: Neuro-DDD并行处理（广播优势）"""
    from neuro_ddd_software import NeuroSignal, AsyncNeuroBus, SoftwareDomain, ProcessingResult
    
    result = BenchmarkResult("Neuro-DDD Parallel Broadcast")
    
    class ParallelDomain(SoftwareDomain):
        def __init__(self, name, delay_ms=5):
            super().__init__(name)
            self.delay_ms = delay_ms
        
        async def async_process_signal(self, signal, context):
            await asyncio.sleep(self.delay_ms / 1000)
            return ProcessingResult(
                success=True,
                result_data=f"{self.domain_name}_processed"
            )
    
    async with AsyncNeuroBus() as bus:
        domains = [
            ParallelDomain("domain_a", delay_ms=5),
            ParallelDomain("domain_b", delay_ms=5),
            ParallelDomain("domain_c", delay_ms=5),
        ]
        
        for domain in domains:
            await domain.set_bus(bus)
        
        result.start_time = time.time()
        
        for i in range(iterations):
            signal = NeuroSignal(
                signal_type="parallel_test",
                source_domain="benchmark",
                target_domains=[d.domain_name for d in domains],
                payload={"iteration": i}
            )
            
            start = time.perf_counter()
            results = await bus.broadcast(signal, wait_for_results=True)
            latency = (time.perf_counter() - start) * 1000
            
            result.add_latency(latency)
        
        result.end_time = time.time()
    
    return result


async def benchmark_traditional_sequential(iterations: int = 100) -> BenchmarkResult:
    """测试2 对照：传统DDD串行调用"""
    result = BenchmarkResult("Traditional DDD Sequential")
    
    class TraditionalHandler:
        def __init__(self, name, delay_ms=5):
            self.name = name
            self.delay_ms = delay_ms
        
        def process(self, data):
            time.sleep(self.delay_ms / 1000)
            return f"{self.name}_processed"
    
    handlers = [
        TraditionalHandler("handler_a", delay_ms=5),
        TraditionalHandler("handler_b", delay_ms=5),
        TraditionalHandler("handler_c", delay_ms=5),
    ]
    
    result.start_time = time.time()
    
    for i in range(iterations):
        start = time.perf_counter()
        
        results = []
        for handler in handlers:
            results.append(handler.process({"iteration": i}))
        
        latency = (time.perf_counter() - start) * 1000
        result.add_latency(latency)
    
    result.end_time = time.time()
    return result


async def benchmark_neuro_dual_mode(iterations: int = 500) -> BenchmarkResult:
    """测试3: Neuro-DDD双模式处理（自适应策略）"""
    from neuro_ddd_software import (
        NeuroSignal, ProcessingMode, ProcessingContext,
        DualModeEngine, DualModeStrategy
    )
    
    result = BenchmarkResult("Neuro-DDD Dual Mode (Adaptive)")
    
    engine = DualModeEngine(strategy=DualModeStrategy.ADAPTIVE)
    
    async def simple_handler(signal, context):
        await asyncio.sleep(0.001)
        return {"result": "fast"}
    
    async def complex_handler(signal, context):
        await asyncio.sleep(0.01)
        return {"result": "complex"}
    
    result.start_time = time.time()
    
    for i in range(iterations):
        is_complex = i % 10 == 0
        signal = NeuroSignal(
            signal_type="dual_mode_test",
            source_domain="benchmark",
            payload={"complex": is_complex, "iteration": i}
        )
        context = ProcessingContext()
        
        start = time.perf_counter()
        await engine.process(signal, context, complex_handler if is_complex else simple_handler)
        latency = (time.perf_counter() - start) * 1000
        
        result.add_latency(latency)
    
    result.end_time = time.time()
    return result


async def benchmark_neuro_error_handling(iterations: int = 200) -> BenchmarkResult:
    """测试4: Neuro-DDD错误处理（熔断器性能）"""
    from neuro_ddd_software import (
        NeuroSignal, AsyncNeuroBus, SoftwareDomain,
        ErrorFeedbackSystem, ErrorContext, ErrorSeverity,
        ProcessingResult, CircuitBreakerConfig
    )
    
    result = BenchmarkResult("Neuro-DDD Error Handling + Circuit Breaker")
    
    feedback = ErrorFeedbackSystem(
        circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=1.0
        )
    )
    
    class ErrorDomain(SoftwareDomain):
        def __init__(self):
            super().__init__("error_domain")
            self.fail_count = 0
        
        async def async_process_signal(self, signal, context):
            self.fail_count += 1
            if self.fail_count % 3 == 0:
                raise ValueError(f"Simulated error #{self.fail_count}")
            return ProcessingResult(success=True)
    
    async with AsyncNeuroBus() as bus:
        domain = ErrorDomain()
        await domain.set_bus(bus)
        
        result.start_time = time.time()
        
        for i in range(iterations):
            signal = NeuroSignal(
                signal_type="error_test",
                source_domain="benchmark",
                payload={"iteration": i}
            )
            
            start = time.perf_counter()
            try:
                await domain.on_receive(signal)
            except Exception:
                await feedback.report_error(
                    ErrorContext(
                        severity=ErrorSeverity.ERROR,
                        source_domain="error_domain",
                        error_type="ValueError",
                        message="Simulated error"
                    ),
                    domain="error_domain"
                )
            latency = (time.perf_counter() - start) * 1000
            
            result.add_latency(latency)
        
        result.end_time = time.time()
    
    return result


async def run_all_benchmarks():
    """运行所有基准测试"""
    print("\n" + "="*70)
    print("  Neuro-DDD vs 传统DDD 真实性能基准测试")
    print("="*70)
    print(f"\n🕐 开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 每个测试迭代次数：1000 (并行测试 100)")
    
    tests = [
        ("简单 CRUD (潜意识)", benchmark_neuro_crud, benchmark_traditional_crud),
        ("并行 vs 串行", benchmark_neuro_parallel, benchmark_traditional_sequential),
        ("双模式处理", benchmark_neuro_dual_mode, None),
        ("错误处理 + 熔断器", benchmark_neuro_error_handling, None),
    ]
    
    all_results = []
    
    for test_name, neuro_fn, traditional_fn in tests:
        print(f"\n{'='*70}")
        print(f"  测试：{test_name}")
        print(f"{'='*70}")
        
        print("\n▶ 运行 Neuro-DDD...")
        neuro_result = await neuro_fn()
        neuro_stats = neuro_result.calculate_stats()
        
        if traditional_fn:
            print("▶ 运行 传统 DDD...")
            traditional_result = await traditional_fn()
            traditional_stats = traditional_result.calculate_stats()
        else:
            traditional_stats = None
        
        print(f"\n📊 结果对比:")
        print(f"\n{'指标':<20} {'Neuro-DDD':>15} {'传统 DDD':>15} {'提升':>10}")
        print(f"{'-'*70}")
        
        metrics = [
            ("平均延迟 (ms)", "avg_ms"),
            ("P95 延迟 (ms)", "p95_ms"),
            ("P99 延迟 (ms)", "p99_ms"),
            ("最小延迟 (ms)", "min_ms"),
            ("最大延迟 (ms)", "max_ms"),
            ("吞吐量 (ops/s)", "throughput_ops"),
        ]
        
        for label, key in metrics:
            neuro_val = neuro_stats.get(key, 0)
            trad_val = traditional_stats.get(key, 0) if traditional_stats else 0
            
            if trad_val > 0 and key in ["avg_ms", "p95_ms", "p99_ms", "min_ms", "max_ms"]:
                improvement = ((trad_val - neuro_val) / trad_val) * 100
                improvement_str = f"{improvement:+.1f}%"
            elif trad_val > 0 and key == "throughput_ops":
                improvement = ((neuro_val - trad_val) / trad_val) * 100
                improvement_str = f"{improvement:+.1f}%"
            else:
                improvement_str = "-"
            
            neuro_str = f"{neuro_val:.2f}" if isinstance(neuro_val, float) else str(neuro_val)
            trad_str = f"{trad_val:.2f}" if isinstance(trad_val, float) else str(trad_val) if trad_val else "N/A"
            
            print(f"{label:<20} {neuro_str:>15} {trad_str:>15} {improvement_str:>10}")
        
        all_results.append((test_name, neuro_stats, traditional_stats))
    
    print(f"\n{'='*70}")
    print("  📈 性能总结")
    print(f"{'='*70}")
    
    total_neuro_throughput = sum(r[1].get("throughput_ops", 0) for r in all_results)
    total_trad_throughput = sum(
        r[2].get("throughput_ops", 0) for r in all_results if r[2]
    )
    
    if total_trad_throughput > 0:
        overall_improvement = ((total_neuro_throughput - total_trad_throughput) / total_trad_throughput) * 100
        print(f"\n✅ 整体吞吐量提升：{overall_improvement:+.1f}%")
    
    avg_latency_improvement = []
    for name, neuro, trad in all_results:
        if trad and neuro:
            improvement = ((trad["avg_ms"] - neuro["avg_ms"]) / trad["avg_ms"]) * 100
            avg_latency_improvement.append(improvement)
    
    if avg_latency_improvement:
        avg_improvement = statistics.mean(avg_latency_improvement)
        print(f"✅ 平均延迟降低：{avg_improvement:.1f}%")
    
    print(f"\n🕐 结束时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    return all_results


if __name__ == "__main__":
    results = asyncio.run(run_all_benchmarks())
    sys.exit(0)
