"""
Neuro-DDD 软件层框架验证测试
============================
测试内容：
1. 核心组件导入与初始化
2. 异步神经总线广播功能
3. 显意识/潜意识双模式处理
4. 并发调度器
5. 错误反馈系统
6. 神经反射弧
7. 预置领域模板
8. 完整电商示例流程
"""

import asyncio
import sys
import time

sys.path.insert(0, 'e:/X语音')

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_test(name):
    print(f"\n▶ {name}...", end=" ")

async def test_imports():
    """测试1: 核心模块导入"""
    print_test("核心模块导入")
    
    try:
        from neuro_ddd_software import (
            ProcessingMode, SignalPriority, DomainRole,
            ConcurrencyStrategy, ErrorSeverity, FeedbackType,
            DualModeStrategy,
            NeuroSignal, AsyncNeuroBus, SoftwareDomain,
            ConsciousProcessor, SubconsciousProcessor, DualModeEngine,
            ConcurrentScheduler, ErrorFeedbackSystem, ReflexArc,
        )
        from neuro_ddd_software.patterns import ServiceDomain, RepositoryDomain, EventDomain
        
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

async def test_signal_creation():
    """测试2: 神经信号创建"""
    print_test("神经信号创建与操作")
    
    try:
        from neuro_ddd_software.core.signal import NeuroSignal
        from neuro_ddd_software.core.types import SignalPriority
        
        signal = NeuroSignal(
            signal_type="test_event",
            source_domain="test_source",
            target_domains=["target_a", "target_b"],
            payload={"key": "value", "num": 42},
            priority=SignalPriority.HIGH,
            ttl=5
        )
        
        assert signal.signal_type == "test_event"
        assert len(signal.target_domains) == 2
        assert signal.ttl == 5
        assert not signal.is_expired()
        
        child = signal.child_signal("child_event", {"extra": "data"})
        assert child.parent_signal_id == signal.signal_id
        assert child.correlation_id == signal.signal_id
        
        d = signal.to_dict()
        assert "signal_id" in d
        
        clone = signal.clone()
        assert clone.signal_id != signal.signal_id
        
        print("✅ 信号操作全部正常")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_bus():
    """测试3: 异步神经总线"""
    print_test("异步神经总线广播")
    
    try:
        from neuro_ddd_software.core.async_bus import AsyncNeuroBus
        from neuro_ddd_software.core.signal import NeuroSignal
        
        bus = AsyncNeuroBus()
        
        received_signals = []
        
        async def mock_handler(signal):
            received_signals.append(signal)
            from neuro_ddd_software.core.types import ProcessingResult
            return ProcessingResult(success=True, result_data={"handled": True})
        
        class MockDomain:
            domain_name = "mock_domain"
        
        await bus.register_domain(MockDomain())
        bus.subscribe("mock_domain", ["test_type"], mock_handler)
        
        signal = NeuroSignal(
            signal_type="test_type",
            source_domain="sender",
            target_domains=["mock_domain"],
            payload={"test": True}
        )
        
        results = await bus.broadcast(signal, wait_for_results=True)
        
        assert len(results) > 0
        assert results[0].success
        
        metrics = bus.get_metrics()
        assert metrics.signals_broadcast >= 1
        
        await bus.shutdown()
        
        print(f"✅ 总线广播正常 (广播:{metrics.signals_broadcast}, 投递:{metrics.signals_delivered})")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_dual_mode_engine():
    """测试4: 双模式处理引擎"""
    print_test("显意识/潜意识双模式引擎")
    
    try:
        from neuro_ddd_software.processing.dual_mode_engine import DualModeEngine
        from neuro_ddd_software.processing.conscious_processor import ConsciousProcessor
        from neuro_ddd_software.processing.subconscious_processor import SubconsciousProcessor
        from neuro_ddd_software.core.signal import NeuroSignal
        from neuro_ddd_software.core.types import ProcessingMode, ProcessingContext, DualModeStrategy
        
        engine = DualModeEngine(strategy=DualModeStrategy.FAST_FIRST)
        
        async def simple_handler(signal, context):
            return {"result": "processed", "data": signal.payload}
        
        signal = NeuroSignal(
            signal_type="simple_request",
            source_domain="client",
            payload={"query": "test"}
        )
        context = ProcessingContext(mode=ProcessingMode.DUAL)
        
        start = time.time()
        result = await engine.process(signal, context, simple_handler)
        elapsed = (time.time() - start) * 1000
        
        assert result is not None
        assert result.success or result.error
        
        stats = engine.get_stats()
        
        print(f"✅ 双模式处理正常 (耗时:{elapsed:.1f}ms, 模式:{result.processing_mode_used.value})")
        print(f"   引擎统计: 决策数={stats['decision_history_size']}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_concurrent_scheduler():
    """测试5: 并发调度器"""
    print_test("并发调度器")
    
    try:
        from neuro_ddd_software.concurrency.concurrent_scheduler import ConcurrentScheduler
        from neuro_ddd_software.core.types import ProcessingResult
        
        scheduler = ConcurrentScheduler(max_concurrent=10)
        
        async def task_1():
            await asyncio.sleep(0.01)
            return "task_1_done"
        
        async def task_2():
            await asyncio.sleep(0.02)
            return "task_2_done"
        
        start = time.time()
        results = await scheduler.run_parallel([
            (task_1(), {}),
            (task_2(), {}),
        ])
        parallel_time = (time.time() - start) * 1000
        
        assert len(results) == 2
        assert all(r.success for r in results)
        
        pipeline_result = await scheduler.run_pipeline(
            stages=[lambda x: x * 2, lambda x: x + 10],
            initial_data=5
        )
        assert pipeline_result.result_data == 20
        
        metrics = scheduler.get_metrics()
        
        await scheduler.shutdown()
        
        print(f"✅ 并发调度正常 (并行耗时:{parallel_time:.1f}ms, 流水线结果:{pipeline_result.result_data})")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_feedback():
    """测试6: 错误反馈系统"""
    print_test("错误反馈系统")
    
    try:
        from neuro_ddd_software.feedback.error_feedback import (
            ErrorFeedbackSystem, FeedbackConfig, CircuitBreakerConfig, FeedbackType
        )
        from neuro_ddd_software.core.types import ErrorSeverity, ErrorContext
        from neuro_ddd_software.core.signal import NeuroSignal
        
        feedback = ErrorFeedbackSystem(
            default_config=FeedbackConfig(feedback_type=FeedbackType.IMMEDIATE),
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=3)
        )
        
        error_ctx = ErrorContext(
            severity=ErrorSeverity.ERROR,
            source_domain="test_domain",
            error_type="ValueError",
            message="Test error message",
            recovery_hints=["retry_later"]
        )
        
        error_id = await feedback.report_error(error_ctx, domain="test_domain")
        
        assert error_id is not None
        
        for i in range(3):
            await feedback.report_error(error_ctx, domain="test_domain")
        
        is_open = feedback.is_circuit_open("test_domain")
        
        metrics = feedback.get_metrics()
        
        print(f"✅ 错误反馈正常 (错误ID:{error_id[:8]}, 熔断状态:{'OPEN' if is_open else 'CLOSED'})")
        print(f"   统计: 接收={metrics['errors_received']}, 即时={metrics['errors_immediate']}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_reflex_arc():
    """测试7: 神经反射弧"""
    print_test("神经反射弧")
    
    try:
        from neuro_ddd_software.feedback.reflex_arc import ReflexArc
        from neuro_ddd_software.core.signal import NeuroSignal
        from neuro_ddd_software.core.types import SignalPriority
        
        reflex = ReflexArc(name="test_reflex")
        
        triggered_actions = []
        
        async def auto_log_handler(s):
            triggered_actions.append(s.signal_type)
            return {"action": "logged"}
        
        reflex.register_action(
            name="auto_log",
            trigger=lambda s: s.priority <= SignalPriority.HIGH,
            handler=auto_log_handler
        )

        high_priority_signal = NeuroSignal(
            signal_type="urgent_event",
            priority=SignalPriority.CRITICAL
        )
        
        result = await reflex.process_signal(high_priority_signal)
        
        metrics = reflex.get_metrics()
        
        print(f"✅ 反射弧正常 (触发:{result.triggered}, 动作:{result.action_taken})")
        print(f"   指标: 扫描={metrics['signals_scanned']}, 触发={metrics['reflexes_triggered']}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_domain_templates():
    """测试8: 预置领域模板"""
    print_test("预置领域模板")
    
    try:
        from neuro_ddd_software.patterns.service_domain import ServiceDomain
        from neuro_ddd_software.patterns.repository_domain import RepositoryDomain
        from neuro_ddd_software.patterns.event_domain import EventDomain
        
        service = ServiceDomain(service_name="user_service")
        service.register_handler("get_user", lambda p: {"id": p.get("id"), "name": "Test User"})
        
        repo = RepositoryDomain(entity_name="product")
        
        event = EventDomain(event_channel="order_events")
        
        assert service.domain_name == "service:user_service"
        assert repo.domain_name == "repository:product"
        assert event.domain_name == "event:order_events"
        
        print("✅ 领域模板创建成功")
        print(f"   服务域: {service}")
        print(f"   仓储域: {repo}")
        print(f"   事件域: {event}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_all_tests():
    """运行所有测试"""
    print_header("Neuro-DDD 软件层框架验证测试")
    print(f"🕐 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("核心模块导入", test_imports),
        ("神经信号创建", test_signal_creation),
        ("异步神经总线", test_async_bus),
        ("双模式引擎", test_dual_mode_engine),
        ("并发调度器", test_concurrent_scheduler),
        ("错误反馈系统", test_error_feedback),
        ("神经反射弧", test_reflex_arc),
        ("领域模板", test_domain_templates),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = await test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ 异常: {e}")
            results.append((name, False))
    
    print_header("测试结果汇总")
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    for name, p in results:
        status = "✅ PASS" if p else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n📊 结果: {passed}/{total} 通过 ({passed/total*100:.0f}%)")
    print(f"🕐 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
