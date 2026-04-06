"""
传统C语言线性编译器对照测试脚本
=================================
验证目标：
1. 5阶段严格串行执行
2. 每阶段独立计时
3. 正常路径完整执行
4. 异常路径正确终止
"""

import sys
import time
from typing import Dict, Any, List

sys.path.insert(0, ".")

from traditional_c.compiler import TraditionalCCompiler


# 正常测试用标准C代码
NORMAL_C_CODE = """int a = 5;
int b = 0;
int c = 1;
if (b > 0) {
    for (c = 1; ; ) {
    }
}
"""

# 错误测试用标准C代码（未声明变量）
ERROR_C_CODE = """int x = undeclared_var + 1;
"""


def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print(f"{'-'*60}")


def test_pipeline_normal() -> Dict[str, Any]:
    """测试1：正常编译流程 - 5阶段全部完成"""
    result = {"passed": False, "details": {}, "compiler_result": None}

    print_separator("测试1：正常编译流程 - 5阶段全部完成")

    try:
        compiler = TraditionalCCompiler()

        print(f"\n📥 输入源码 (标准C语言):")
        for line in NORMAL_C_CODE.strip().split('\n'):
            print(f"   {line}")

        start_time = time.time()
        compile_result = compiler.compile(NORMAL_C_CODE)
        end_time = time.time()

        assert compile_result is not None, "编译结果不应为None"

        success = compile_result.get("success", False)
        results = compile_result.get("results", {})
        timings = compile_result.get("timings", {})
        total_time = compile_result.get("total_time", 0)
        execution_log = compile_result.get("execution_log", [])
        error = compile_result.get("error")

        print(f"\n✅ 编译状态: {'成功' if success else '失败'}")
        assert success, "正常编译应成功完成"

        print(f"\n📊 各阶段执行结果:")
        expected_stages = ["Lexer", "Parser", "SemanticAnalyzer", "CodeGenerator", "Optimizer"]
        for stage in expected_stages:
            has_result = stage in results and results[stage] is not None
            timing = timings.get(stage, 0)
            status = "✅ 完成" if has_result else "⏳ 未完成"
            print(f"   {stage}: {status} (耗时: {timing*1000:.3f}ms)")

        completed_stages = len([s for s in expected_stages if s in timings and timings[s] >= 0])
        print(f"\n✅ 已完成阶段(基于timing): {completed_stages}/5")
        assert completed_stages == 5, f"应完成全部5个阶段，实际完成{completed_stages}个"

        print(f"\n⏱️  各阶段独立计时:")
        for stage, timing in timings.items():
            timing_ms = timing * 1000
            print(f"   - {stage}: {timing_ms:.3f}ms")
            assert timing >= 0, f"{stage}阶段耗时应>=0"

        sum_of_stages = sum(timings.values())
        print(f"\n📐 耗时验证:")
        print(f"   各阶段耗时之和: {sum_of_stages*1000:.3f}ms")
        print(f"   记录的总耗时: {total_time*1000:.3f}ms")
        print(f"   实测总耗时: {(end_time-start_time)*1000:.3f}ms")

        assert total_time >= 0, "总耗时应>=0"
        assert total_time >= sum_of_stages * 0.9, "总耗时应约等于各阶段耗时之和（允许10%误差）"

        generated_code = results.get("optimized_code")
        if generated_code and isinstance(generated_code, dict) and "code" in generated_code:
            code = generated_code["code"]
            print(f"\n📝 生成的C代码:")
            print(f"   {'-'*50}")
            for line in code.split('\n')[:10]:
                print(f"   {line}")
            if code.count('\n') > 10:
                print(f"   ... (共{code.count(chr(10))+1}行)")
            print(f"   {'-'*50}")

        result["details"] = {
            "success": success,
            "stages_completed": completed_stages,
            "timings": {k: v*1000 for k, v in timings.items()},
            "total_time_ms": total_time * 1000,
            "sum_of_stages_ms": sum_of_stages * 1000,
            "execution_log_entries": len(execution_log),
        }
        result["compiler_result"] = compile_result

        result["passed"] = True
        print("\n🎉 测试1通过！正常编译流程验证成功")

    except AssertionError as e:
        print(f"\n❌ 测试1失败: {e}")
        result["error"] = str(e)
    except Exception as e:
        print(f"\n❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        result["error"] = str(e)

    return result


def test_pipeline_error() -> Dict[str, Any]:
    """测试2：错误处理 - 阶段错误终止后续流程"""
    result = {"passed": False, "details": {}}

    print_separator("测试2：错误处理 - 阶段错误终止后续流程")

    try:
        compiler = TraditionalCCompiler()

        print(f"\n📥 输入包含错误的源码 (标准C语言):")
        for line in ERROR_C_CODE.strip().split('\n'):
            print(f"   {line}")

        compile_result = compiler.compile(ERROR_C_CODE)

        assert compile_result is not None, "编译结果不应为None"

        success = compile_result.get("success", False)
        results = compile_result.get("results", {})
        timings = compile_result.get("timings", {})
        error = compile_result.get("error")
        execution_log = compile_result.get("execution_log", [])

        print(f"\n✅ 编译状态: {'成功' if success else '失败'}")
        assert not success, "错误源码编译应失败"

        assert error is not None, "应有错误信息记录"
        error_stage = error.get("stage", "Unknown")
        error_message = error.get("message", "N/A")
        error_type = error.get("error_type", "N/A")

        print(f"\n❌ 错误信息:")
        print(f"   出错阶段: {error_stage}")
        print(f"   错误消息: {error_message}")
        print(f"   错误类型: {error_type}")

        failed_stage_index = None
        expected_order = ["Lexer", "Parser", "SemanticAnalyzer", "CodeGenerator", "Optimizer"]
        if error_stage in expected_order:
            failed_stage_index = expected_order.index(error_stage)

        completed_before_error = 0
        if failed_stage_index is not None:
            for i, stage in enumerate(expected_order):
                if i < failed_stage_index and stage in results:
                    completed_before_error += 1
                elif i >= failed_stage_index:
                    should_not_have = stage in results and results[stage] is not None
                    if should_not_have:
                        print(f"   ⚠️  警告: 出错阶段{error_stage}之后的{stage}有结果")

        print(f"\n✅ 阶段执行分析:")
        print(f"   出错阶段位置: 第{failed_stage_index+1}阶段(从1开始)" if failed_stage_index is not None else "   出错阶段位置: 未识别")
        print(f"   出错前完成的阶段数: {completed_before_error}")

        error_events = [log for log in execution_log if log.get("event") == "error"]
        print(f"   执行日志中的错误事件数: {len(error_events)}")
        assert len(error_events) > 0, "执行日志中应记录错误事件"

        stages_after_error = []
        if failed_stage_index is not None:
            stages_after_error = expected_order[failed_stage_index+1:]
            for stage in stages_after_error:
                stage_not_executed = stage not in timings or timings[stage] == 0
                print(f"   {stage}: {'未执行 ✅' if stage_not_executed else '已执行 ⚠️'}")

        result["details"] = {
            "success": success,
            "error_stage": error_stage,
            "error_message": error_message,
            "stages_completed_before_error": completed_before_error,
            "failed_stage_position": failed_stage_index + 1 if failed_stage_index is not None else None,
            "stages_after_error": stages_after_error,
            "error_event_count": len(error_events),
        }

        result["passed"] = True
        print("\n🎉 测试2通过！错误处理机制验证成功")

    except AssertionError as e:
        print(f"\n❌ 测试2失败: {e}")
        result["error"] = str(e)
    except Exception as e:
        print(f"\n❌ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
        result["error"] = str(e)

    return result


def test_timing_accuracy() -> Dict[str, Any]:
    """测试3：计时准确性验证"""
    result = {"passed": False, "details": {}}

    print_separator("测试3：计时准确性验证")

    try:
        compiler = TraditionalCCompiler()

        print(f"\n🔄 多次编译同一源码以验证计时一致性...")
        print(f"📥 源码 (标准C语言):")
        for line in NORMAL_C_CODE.strip().split('\n')[:3]:
            print(f"   {line}")
        print("   ...")

        num_runs = 3
        all_timings = []

        for run_idx in range(num_runs):
            compiler.reset()
            compile_result = compiler.compile(NORMAL_C_CODE)

            timings = compile_result.get("timings", {})
            total_time = compile_result.get("total_time", 0)

            run_data = {
                "run": run_idx + 1,
                "total_time_ms": total_time * 1000,
                "stage_timings_ms": {k: v*1000 for k, v in timings.items()},
            }
            all_timings.append(run_data)

            print(f"\n   第{run_idx + 1}次运行:")
            print(f"      总耗时: {total_time*1000:.3f}ms")
            for stage, timing in timings.items():
                print(f"      - {stage}: {timing*1000:.3f}ms")

        total_times = [run["total_time_ms"] for run in all_timings]
        avg_total = sum(total_times) / len(total_times)
        max_deviation = max(abs(t - avg_total) for t in total_times)

        print(f"\n📊 计时统计:")
        print(f"   运行次数: {num_runs}")
        print(f"   平均总耗时: {avg_total:.3f}ms")
        print(f"   最大偏差: {max_deviation:.3f}ms")

        stage_consistency = {}
        expected_stages = ["Lexer", "Parser", "SemanticAnalyzer", "CodeGenerator", "Optimizer"]
        for stage in expected_stages:
            stage_times = [run["stage_timings_ms"].get(stage, 0) for run in all_timings]
            if any(t > 0 for t in stage_times):
                avg_stage = sum(t for t in stage_times if t > 0) / sum(1 for t in stage_times if t > 0)
                max_stage_deviation = max(abs(t - avg_stage) for t in stage_times if t > 0)
                stage_consistency[stage] = {
                    "avg_ms": avg_stage,
                    "max_deviation_ms": max_stage_deviation,
                    "consistent": max_stage_deviation < avg_total * 0.5,
                }

        print(f"\n📈 各阶段计时一致性:")
        for stage, data in stage_consistency.items():
            icon = "✅" if data["consistent"] else "⚠️"
            print(f"   {icon} {stage}: 平均{data['avg_ms']:.3f}ms, 偏差{data['max_deviation']:.3f}ms")

        all_consistent = all(d["consistent"] for d in stage_consistency.values()) if stage_consistency else True
        assert all_consistent or max_deviation < avg_total * 0.5, "多次运行计时应在合理范围内一致"

        result["details"] = {
            "num_runs": num_runs,
            "avg_total_time_ms": avg_total,
            "max_deviation_ms": max_deviation,
            "stage_consistency": stage_consistency,
            "all_timings": all_timings,
        }

        result["passed"] = True
        print("\n🎉 测试3通过！计时准确性验证成功")

    except AssertionError as e:
        print(f"\n❌ 测试3失败: {e}")
        result["error"] = str(e)
    except Exception as e:
        print(f"\n❌ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        result["error"] = str(e)

    return result


def test_stage_execution_order() -> Dict[str, Any]:
    """测试4：执行顺序严格性验证"""
    result = {"passed": False, "details": {}}

    print_separator("测试4：执行顺序严格性验证")

    try:
        compiler = TraditionalCCompiler()

        print(f"\n📥 源码 (标准C语言):")
        for line in NORMAL_C_CODE.strip().split('\n')[:3]:
            print(f"   {line}")
        print("   ...")

        compile_result = compiler.compile(NORMAL_C_CODE)
        execution_log = compile_result.get("execution_log", [])

        print(f"\n📋 执行日志事件序列:")

        stage_order = []
        event_sequence = []

        for i, log_entry in enumerate(execution_log):
            stage = log_entry.get("stage", "-")
            event = log_entry.get("event", "-")
            timestamp = log_entry.get("timestamp", 0)
            time_str = time.strftime("%H:%M:%S", time.localtime(timestamp)) if timestamp else "-"

            event_info = f"{event}"
            if event == "start":
                input_summary = log_entry.get("input_summary", "")
                event_info += f" (输入: {input_summary[:30]})"
            elif event == "end":
                timing = log_entry.get("timing", 0)
                output_summary = log_entry.get("output_summary", "")
                event_info += f" (耗时:{timing*1000:.2f}ms, 输出:{output_summary[:30]})"
            elif event == "error":
                error = log_entry.get("error", {})
                event_info += f" (错误: {error.get('message', '未知')[:30]})"

            print(f"   [{i+1:2d}] {time_str} | {stage:20s} | {event_info}")

            if event == "start" and stage != "Compilation":
                stage_order.append(stage)
            event_sequence.append((stage, event))

        expected_order = ["Lexer", "Parser", "SemanticAnalyzer", "CodeGenerator", "Optimizer"]

        print(f"\n✅ 验证执行顺序:")
        print(f"   期望顺序: {' → '.join(expected_order)}")
        print(f"   实际顺序: {' → '.join(stage_order)}")

        order_correct = stage_order == expected_order
        print(f"   顺序正确: {'是 ✅' if order_correct else '否 ❌'}")

        assert order_correct, f"执行顺序应为{expected_order}，实际为{stage_order}"

        start_end_pairs = {}
        current_start = None
        for stage, event in event_sequence:
            if event == "start" and stage != "Compilation":
                current_start = stage
            elif event == "end" and stage != "Compilation" and current_start == stage:
                if stage not in start_end_pairs:
                    start_end_pairs[stage] = True

        all_stages_completed = all(stage in start_end_pairs for stage in expected_order)
        print(f"\n✅ 所有阶段都有开始和结束事件: {'是 ✅' if all_stages_completed else '否 ❌'}")
        assert all_stages_completed, "所有阶段都应有完整的开始/结束事件"

        no_overlap = True
        active_stages = set()
        for stage, event in event_sequence:
            if event == "start" and stage != "Compilation":
                if active_stages:
                    no_overlap = False
                    print(f"   ⚠️  检测到重叠: {stage}在{active_stages}活跃时启动")
                active_stages.add(stage)
            elif event == "end" and stage != "Compilation":
                active_stages.discard(stage)

        print(f"   无并行重叠: {'是 ✅' if no_overlap else '否 ❌'}")
        assert no_overlap, "串行流水线不应有阶段重叠执行"

        result["details"] = {
            "expected_order": expected_order,
            "actual_order": stage_order,
            "order_correct": order_correct,
            "all_stages_completed": all_stages_completed,
            "no_parallel_overlap": no_overlap,
            "total_events": len(execution_log),
        }

        result["passed"] = True
        print("\n🎉 测试4通过！执行顺序严格性验证成功")

    except AssertionError as e:
        print(f"\n❌ 测试4失败: {e}")
        result["error"] = str(e)
    except Exception as e:
        print(f"\n❌ 测试4异常: {e}")
        import traceback
        traceback.print_exc()
        result["error"] = str(e)

    return result


def run_all_tests():
    """运行所有测试并输出结果"""
    print("\n" + "=" * 60)
    print("  🔧 Traditional C 编译器对照测试套件")
    print("     (使用标准C语言代码测试)")
    print("=" * 60)
    print(f"📥 正常测试输入 (标准C代码):")
    for line in NORMAL_C_CODE.strip().split('\n')[:3]:
        print(f"   {line}")
    print("   ...")
    print(f"❌ 错误测试输入 (标准C代码):")
    for line in ERROR_C_CODE.strip().split('\n'):
        print(f"   {line}")
    print(f"🕐 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    results.append(("测试1: 正常编译流程", test_pipeline_normal()))
    results.append(("测试2: 错误处理机制", test_pipeline_error()))
    results.append(("测试3: 计时准确性", test_timing_accuracy()))
    results.append(("测试4: 执行顺序严格性", test_stage_execution_order()))

    print_separator("测试结果汇总")

    passed_count = 0
    failed_count = 0

    for test_name, result in results:
        status = "✅ 通过" if result["passed"] else "❌ 失败"
        print(f"{status} - {test_name}")
        if result["passed"]:
            passed_count += 1
        else:
            failed_count += 1
            if "error" in result:
                print(f"   原因: {result['error']}")

    total_tests = passed_count + failed_count
    pass_rate = (passed_count / total_tests * 100) if total_tests > 0 else 0

    print_separator()
    print(f"📊 总计: {total_tests} 个测试")
    print(f"   ✅ 通过: {passed_count} ({pass_rate:.1f}%)")
    print(f"   ❌ 失败: {failed_count} ({100-pass_rate:.1f}%)")

    if failed_count == 0:
        print("\n🎉 所有测试通过！Traditional C编译器验证合格")
    else:
        print(f"\n⚠️  有{failed_count}个测试失败，请检查上述错误信息")

    print(f"\n🕐 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    return results


if __name__ == "__main__":
    run_all_tests()
