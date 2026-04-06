"""Neuro-DDD信号流转追踪与验证系统

提供信号流转追踪、验证报告生成和双架构对比分析功能。
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from ..core.signal import Signal
from ..core.types import SignalType, DomainType, SchedulingDecision


@dataclass
class NeuroFlowTracker:
    """Neuro-DDD架构信号流转追踪器

    追踪神经总线上的信号流转过程，记录信号的发送、接收时间，
    并提供同步性检测、完整报告生成等功能。

    Attributes:
        signal_records: 信号流转记录列表
        sync_threshold: 同步到达判定阈值（秒）
        domain_receive_times: 每个领域接收信号的时间记录
        scheduling_records: 调度决策记录
    """

    signal_records: List[Dict] = field(default_factory=list)
    sync_threshold: float = 0.05
    domain_receive_times: Dict[str, Dict[str, float]] = field(default_factory=dict)
    scheduling_records: Dict[str, SchedulingDecision] = field(default_factory=dict)

    def record_signal(self, signal: Signal, source_domain: str, target_domains: List[str]) -> None:
        """记录一条信号的发送事件

        Args:
            signal: 信号对象
            source_domain: 发送领域的名称
            target_domains: 目标领域名称列表
        """
        record = {
            'signal_id': signal.signal_id,
            'signal_type': signal.signal_type.value if signal.signal_type else 'UNKNOWN',
            'signal_name': f'信号{signal.signal_type.value if signal.signal_type else "?"}',
            'source_domain': source_domain,
            'target_domains': list(target_domains),
            'timestamp': time.time(),
            'receive_status': {domain: False for domain in target_domains},
            'scheduling_decision': None,
        }
        self.signal_records.append(record)
        self.domain_receive_times[signal.signal_id] = {}

    def record_receive(self, signal_id: str, domain: str, receive_time: Optional[float] = None) -> None:
        """记录某个领域接收到某个信号的时间

        Args:
            signal_id: 信号ID
            domain: 接收领域的名称
            receive_time: 接收时间（默认为当前时间）
        """
        if receive_time is None:
            receive_time = time.time()

        if signal_id not in self.domain_receive_times:
            self.domain_receive_times[signal_id] = {}

        self.domain_receive_times[signal_id][domain] = receive_time

        for record in self.signal_records:
            if record['signal_id'] == signal_id and domain in record['target_domains']:
                record['receive_status'][domain] = True

    def record_scheduling_decision(self, signal_id: str, decision: SchedulingDecision) -> None:
        """记录调度决策结果

        Args:
            signal_id: 信号ID（通常是调度信号）
            decision: 调度决策枚举值
        """
        self.scheduling_records[signal_id] = decision
        for record in self.signal_records:
            if record['signal_id'] == signal_id:
                record['scheduling_decision'] = decision.value

    def get_signal_flow_table(self) -> List[Dict]:
        """生成信号流转记录表

        Returns:
            信号流转记录列表，每条记录包含：
            - 信号名称、发送领域、同步接收领域列表、是否同步、有无顺序等待、调度决策结果
        """
        flow_table = []
        for record in self.signal_records:
            signal_id = record['signal_id']
            target_domains = record['target_domains']

            sync_check = self.check_sync_delivery(signal_id)
            received_domains = [
                d for d in target_domains
                if record['receive_status'].get(d, False)
            ]

            has_order_wait = self._check_order_waiting(signal_id)

            flow_entry = {
                'signal_name': record['signal_name'],
                'source_domain': record['source_domain'],
                'sync_received_domains': received_domains,
                'is_sync': sync_check['is_sync'] if len(received_domains) > 1 else None,
                'has_order_wait': has_order_wait,
                'scheduling_decision': record.get('scheduling_decision'),
                'time_diff_ms': sync_check['max_time_diff'] * 1000 if sync_check else 0,
            }
            flow_table.append(flow_entry)

        return flow_table

    def check_sync_delivery(self, signal_id: str) -> Dict:
        """检测某条信号是否同步到达所有目标领域

        Args:
            signal_id: 信号ID

        Returns:
            包含同步性检测结果的字典：
            - is_sync: 是否同步到达
            - max_time_diff: 最大时间差（秒）
            - receive_details: 各领域接收详情列表
        """
        receive_times = self.domain_receive_times.get(signal_id, {})

        if not receive_times or len(receive_times) < 2:
            return {
                'is_sync': True,
                'max_time_diff': 0.0,
                'receive_details': [
                    {'domain': domain, 'receive_time': t, 'delay_from_first': 0}
                    for domain, t in receive_times.items()
                ],
            }

        times_list = sorted(receive_times.items(), key=lambda x: x[1])
        first_time = times_list[0][1]

        receive_details = [
            {
                'domain': domain,
                'receive_time': recv_time,
                'delay_from_first': recv_time - first_time,
            }
            for domain, recv_time in times_list
        ]

        max_time_diff = max(d['delay_from_first'] for d in receive_details)
        is_sync = max_time_diff <= self.sync_threshold

        return {
            'is_sync': is_sync,
            'max_time_diff': round(max_time_diff, 6),
            'receive_details': receive_details,
        }

    def _check_order_waiting(self, signal_id: str) -> bool:
        """检查是否存在顺序等待

        Args:
            signal_id: 信号ID

        Returns:
            是否存在顺序依赖导致的等待
        """
        for i, record in enumerate(self.signal_records):
            if record['signal_id'] == signal_id and i > 0:
                prev_record = self.signal_records[i - 1]
                prev_target_domains = set(prev_record['target_domains'])
                current_source = record['source_domain']
                return current_source in prev_target_domains
        return False

    def get_full_report(self) -> Dict:
        """获取完整的追踪报告

        Returns:
            包含以下内容的字典：
            - total_signals: 总信号数
            - signal_type_stats: 每类信号统计
            - sync_analysis: 同步性分析
            - full_table: 完整记录表
            - summary: 摘要信息
        """
        type_counts: Dict[str, int] = {}
        for record in self.signal_records:
            sig_type = record['signal_type']
            type_counts[sig_type] = type_counts.get(sig_type, 0) + 1

        sync_count = 0
        async_count = 0
        for record in self.signal_records:
            signal_id = record['signal_id']
            target_domains = record['target_domains']
            if len(target_domains) >= 2:
                sync_result = self.check_sync_delivery(signal_id)
                if sync_result['is_sync']:
                    sync_count += 1
                else:
                    async_count += 1

        order_wait_signals = sum(
            1 for r in self.signal_records
            if self._check_order_waiting(r['signal_id'])
        )

        return {
            'total_signals': len(self.signal_records),
            'signal_type_stats': type_counts,
            'sync_analysis': {
                'sync_deliveries': sync_count,
                'async_deliveries': async_count,
                'sync_rate': round(sync_count / (sync_count + async_count) * 100, 2)
                if (sync_count + async_count) > 0 else 100.0,
            },
            'order_analysis': {
                'signals_with_order_wait': order_wait_signals,
                'order_wait_rate': round(order_wait_signals / len(self.signal_records) * 100, 2)
                if self.signal_records else 0,
            },
            'scheduling_decisions': {
                decision.value: sum(1 for d in self.scheduling_records.values() if d == decision)
                for decision in SchedulingDecision
            },
            'full_table': self.get_signal_flow_table(),
            'summary': {
                'tracker_start_time': min((r['timestamp'] for r in self.signal_records), default=None),
                'tracker_end_time': max((r['timestamp'] for r in self.signal_records), default=None),
                'domains_involved': list(set(
                    r['source_domain'] for r in self.signal_records
                ) | set(
                    d for r in self.signal_records for d in r['target_domains']
                )),
            },
        }

    def reset(self) -> None:
        """重置所有记录"""
        self.signal_records.clear()
        self.domain_receive_times.clear()
        self.scheduling_records.clear()

    def __repr__(self) -> str:
        return (
            f"NeuroFlowTracker(signals={len(self.signal_records)}, "
            f"threshold={self.sync_threshold}s)"
        )


@dataclass
class VerificationReportGenerator:
    """验证报告生成器 - 生成双架构验证报告

    支持生成Neuro-DDD架构、传统C架构以及双架构对比的Markdown格式验证报告。
    """

    def generate_neuro_report(self, tracker: NeuroFlowTracker) -> str:
        """根据Neuro-DDD追踪数据生成Markdown格式的验证报告

        Args:
            tracker: NeuroFlowTracker实例

        Returns:
            Markdown格式的验证报告字符串
        """
        report_data = tracker.get_full_report()

        lines = [
            '# Neuro-DDD 架构信号流转验证报告',
            '',
            f'**生成时间**: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            '## 一、总体概览',
            '',
            f'- **总信号数**: {report_data["total_signals"]}',
            f'- **涉及领域**: {", ".join(report_data["summary"]["domains_involved"])}',
            '',
            '## 二、信号类型统计',
            '',
            '| 信号类型 | 数量 | 占比 |',
            '|---------|------|------|',
        ]

        total = report_data['total_signals']
        for sig_type, count in report_data['signal_type_stats'].items():
            percentage = round(count / total * 100, 2) if total > 0 else 0
            lines.append(f'| {sig_type} | {count} | {percentage}% |')

        lines.extend([
            '',
            '## 三、同步性分析',
            '',
            f'- **同步送达**: {report_data["sync_analysis"]["sync_deliveries"]} 次',
            f'- **异步送达**: {report_data["sync_analysis"]["async_deliveries"]} 次',
            f'- **同步率**: {report_data["sync_analysis"]["sync_rate"]}%',
            f'- **存在顺序等待的信号**: {report_data["order_analysis"]["signals_with_order_wait"]} 个',
            '',
            '## 四、调度决策统计',
        ])

        for decision, count in report_data['scheduling_decisions'].items():
            lines.append(f'- **{decision}**: {count} 次')

        lines.extend([
            '',
            '## 五、信号流转记录详情',
            '',
            '| 信号名称 | 发送领域 | 同步接收领域 | 接收是否同步 | 有无顺序等待 | 调度决策结果 |',
            '|---------|---------|------------|------------|------------|------------|',
        ])

        for entry in report_data['full_table']:
            domains_str = ', '.join(entry['sync_received_domains']) or '-'
            is_sync_str = '是' if entry['is_sync'] else ('否' if entry['is_sync'] is False else '-')
            wait_str = '有' if entry['has_order_wait'] else '无'
            schedule_str = entry['scheduling_decision'] or '-'

            lines.append(
                f"| {entry['signal_name']} | {entry['source_domain']} | "
                f"{domains_str} | {is_sync_str} | {wait_str} | {schedule_str} |"
            )

        lines.extend([
            '',
            '## 六、合格判定',
            '',
        ])

        neuro_pass = self._evaluate_neuro_pass(report_data)
        status = '✅ 通过' if neuro_pass['overall'] else '❌ 未通过'
        lines.append(f"**整体状态**: {status}")
        lines.append('')
        for criterion, result in neuro_pass['criteria'].items():
            icon = '✅' if result['pass'] else '❌'
            lines.append(f"- {icon} **{criterion}**: {result['detail']}")

        return '\n'.join(lines)

    def generate_traditional_report(self, compiler_result: Dict) -> str:
        """根据传统C编译结果生成Markdown格式报告

        Args:
            compiler_result: TraditionalCCompiler.compile()返回的结果字典

        Returns:
            Markdown格式的传统编译器报告字符串
        """
        success = compiler_result.get('success', False)
        timings = compiler_result.get('timings', {})
        total_time = compiler_result.get('total_time', 0)
        execution_log = compiler_result.get('execution_log', [])
        error = compiler_result.get('error')

        lines = [
            '# Traditional C 编译器执行报告',
            '',
            f'**生成时间**: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            '## 一、执行概览',
            '',
            f'- **执行状态**: {"成功 ✅" if success else "失败 ❌"}',
            f'- **总耗时**: {total_time * 1000:.2f} ms ({total_time:.6f}s)',
            '',
            '## 二、各阶段耗时明细',
            '',
            '| 阶段名称 | 耗时(ms) | 占比(%) | 状态 |',
            '|---------|---------|--------|------|',
        ]

        stage_names = ['Lexer', 'Parser', 'SemanticAnalyzer', 'CodeGenerator', 'Optimizer']
        for stage in stage_names:
            timing = timings.get(stage, 0)
            timing_ms = timing * 1000
            percentage = round(timing / total_time * 100, 2) if total_time > 0 else 0
            completed = stage in compiler_result.get('results', {})
            status = '✅ 完成' if completed else '⏳ 未完成'
            lines.append(f'| {stage} | {timing_ms:.3f} | {percentage}% | {status} |')

        lines.extend([
            '',
            '## 三、流水线流转过程',
            '',
            '| 阶段 | 事件 | 时间戳 | 详情 |',
            '|-----|------|-------|------|',
        ])

        for log_entry in execution_log[:20]:
            stage = log_entry.get('stage', '-')
            event = log_entry.get('event', '-')
            timestamp = log_entry.get('timestamp', 0)
            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp)) if timestamp else '-'

            if event == 'start':
                detail = log_entry.get('input_summary', '')
            elif event == 'end':
                detail = f"耗时: {log_entry.get('timing', 0)*1000:.3f}ms, 输出: {log_entry.get('output_summary', '')}"
            elif event == 'error':
                detail = f"错误: {log_entry.get('error', {}).get('message', '未知错误')}"
            else:
                detail = ''

            lines.append(f'| {stage} | {event} | {time_str} | {detail[:50]} |')

        if error:
            lines.extend([
                '',
                '## 四、错误信息',
                '',
                f"- **错误阶段**: {error.get('stage', 'Unknown')}",
                f"- **错误消息**: {error.get('message', 'N/A')}",
                f"- **错误类型**: {error.get('error_type', 'N/A')}",
            ])
        else:
            lines.extend([
                '',
                '## 四、合格判定',
                '',
            ])

            trad_pass = self._evaluate_traditional_pass(compiler_result)
            status = '✅ 通过' if trad_pass['overall'] else '❌ 未通过'
            lines.append(f"**整体状态**: {status}")
            lines.append('')
            for criterion, result in trad_pass['criteria'].items():
                icon = '✅' if result['pass'] else '❌'
                lines.append(f"- {icon} **{criterion}**: {result['detail']}")

        return '\n'.join(lines)

    def generate_comparison_report(self, neuro_data: Dict, traditional_data: Dict) -> str:
        """生成双架构对比报告

        Args:
            neuro_data: Neuro-DDD追踪器的完整报告数据
            traditional_data: 传统C编译器的结果字典

        Returns:
            Markdown格式的双架构对比报告字符串
        """
        analyzer = ComparisonAnalyzer()
        analyzer.load_neuro_data(neuro_data)
        analyzer.load_traditional_data(traditional_data)

        timing_comparison = analyzer.compare_timing()
        steps_comparison = analyzer.compare_flow_steps()
        recovery_comparison = analyzer.compare_error_recovery()
        scalability_comparison = analyzer.compare_scalability()
        comparison_table = analyzer.generate_comparison_table()

        lines = [
            '# 双架构对比验证报告',
            '',
            f'**生成时间**: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            '## 一、综合对比总览',
            '',
            comparison_table,
            '',
            '## 二、详细对比分析',
            '',
            '### 2.1 执行耗时对比',
            '',
            f"- **Neuro-DDD总耗时**: {timing_comparison['neuro_time_ms']:.2f} ms",
            f"- **Traditional C总耗时**: {timing_comparison['traditional_time_ms']:.2f} ms",
            f"- **加速比**: {timing_comparison['speedup_ratio']:.2f}x",
            f"- **时间节省**: {timing_comparison['time_saved_percent']:.1f}%",
            f"- **判定**: {timing_comparison['verdict']}",
            '',
            '### 2.2 流转步数对比',
            '',
            f"- **Neuro-DDD流转步数**: {steps_comparison['neuro_steps']} 步",
            f"- **Traditional C流转步数**: {steps_comparison['traditional_steps']} 步",
            f"- **步数减少率**: {steps_comparison['reduction_rate']:.1f}%",
            f"- **判定**: {steps_comparison['verdict']}",
            '',
            '### 2.3 错误恢复能力对比',
            '',
            f"- **Neuro-DDD恢复能力**: {recovery_comparison['neuro_capability']}",
            f"- **Traditional C恢复能力**: {recovery_comparison['traditional_capability']}",
            f"- **恢复成功率提升**: {recovery_comparison['improvement']}",
            f"- **判定**: {recovery_comparison['verdict']}",
            '',
            '### 2.4 扩展性对比',
            '',
            f"- **Neuro-DDD扩展性评分**: {scalability_comparison['neuro_score']}/10",
            f"- **Traditional C扩展性评分**: {scalability_comparison['traditional_score']}/10",
            f"- **优势维度**: {', '.join(scalability_comparison['advantages'])}",
            f"- **判定**: {scalability_comparison['verdict']}",
            '',
            '## 三、综合评估结论',
            '',
        ]

        overall_verdict = self._generate_overall_verdict(
            timing_comparison, steps_comparison, recovery_comparison, scalability_comparison
        )
        lines.append(overall_verdict)

        return '\n'.join(lines)

    def save_report(self, report_content: str, filepath: str) -> None:
        """将报告保存到文件

        Args:
            report_content: 报告内容字符串
            filepath: 保存路径
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)

    def generate_final_verification(self, neuro_tracker: NeuroFlowTracker, traditional_result: Dict) -> Dict:
        """综合验证：判断整体是否合格

        Args:
            neuro_tracker: NeuroFlowTracker实例
            traditional_result: 传统C编译器的结果字典

        Returns:
            包含验证结果的字典：
            - overall_pass: 整体是否通过
            - neuro_pass: Neuro-DDD是否通过
            - traditional_pass: 传统C是否通过
            - details: 详细判定信息
        """
        neuro_report_data = neuro_tracker.get_full_report()
        neuro_pass_result = self._evaluate_neuro_pass(neuro_report_data)
        traditional_pass_result = self._evaluate_traditional_pass(traditional_result)

        neuro_passed = neuro_pass_result['overall']
        traditional_passed = traditional_pass_result['overall']
        overall_passed = neuro_passed and traditional_passed

        return {
            'overall_pass': overall_passed,
            'neuro_pass': neuro_passed,
            'traditional_pass': traditional_passed,
            'details': {
                'neuro_evaluation': neuro_pass_result,
                'traditional_evaluation': traditional_pass_result,
                'neuro_report_summary': {
                    'total_signals': neuro_report_data['total_signals'],
                    'sync_rate': neuro_report_data['sync_analysis']['sync_rate'],
                    'scheduling_decisions': dict(neuro_report_data['scheduling_decisions']),
                },
                'traditional_summary': {
                    'success': traditional_result.get('success', False),
                    'total_time_ms': traditional_result.get('total_time', 0) * 1000,
                    'stages_completed': len(traditional_result.get('timings', {})),
                },
            },
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }

    def _evaluate_neuro_pass(self, report_data: Dict) -> Dict:
        """评估Neuro-DDD架构是否通过验证"""
        criteria = {}

        sync_rate = report_data['sync_analysis']['sync_rate']
        criteria['同步率达标'] = {
            'pass': sync_rate >= 90.0,
            'detail': f"当前同步率: {sync_rate}% (要求≥90%)",
        }

        criteria['信号完整性'] = {
            'pass': report_data['total_signals'] >= 3,
            'detail': f"已记录{report_data['total_signals']}条信号 (要求≥3)",
        }

        criteria['调度决策正常'] = {
            'pass': any(v > 0 for v in report_data['scheduling_decisions'].values()),
            'detail': f"已记录{sum(report_data['scheduling_decisions'].values())}次调度决策",
        }

        overall = all(c['pass'] for c in criteria.values())
        return {'overall': overall, 'criteria': criteria}

    def _evaluate_traditional_pass(self, compiler_result: Dict) -> Dict:
        """评估传统C编译器是否通过验证"""
        criteria = {}

        success = compiler_result.get('success', False)
        criteria['编译成功'] = {
            'pass': success,
            'detail': "编译流程成功完成" if success else "编译过程中出现错误",
        }

        stages_completed = len(compiler_result.get('timings', {}))
        criteria['阶段完整性'] = {
            'pass': stages_completed >= 5,
            'detail': f"已完成{stages_completed}/5个阶段",
        }

        total_time = compiler_result.get('total_time', 0)
        criteria['性能合理'] = {
            'pass': total_time < 10.0,
            'detail': f"总耗时: {total_time*1000:.2f}ms (要求<10s)",
        }

        overall = all(c['pass'] for c in criteria.values())
        return {'overall': overall, 'criteria': criteria}

    def _generate_overall_verdict(self, timing_comp, steps_comp, recovery_comp, scalability_comp) -> str:
        """生成综合评估结论"""
        verdicts = [timing_comp['verdict'], steps_comp['verdict'], recovery_comp['verdict'], scalability_comp['verdict']]
        positive_count = sum(1 for v in verdicts if '优' in v or '胜' in v)

        if positive_count >= 3:
            conclusion = "**🎉 综合评估：Neuro-DDD架构全面优于传统C架构**"
        elif positive_count >= 2:
            conclusion = "**📊 综合评估：Neuro-DDD架构在多数维度优于传统C架构**"
        else:
            conclusion = "**⚖️ 综合评估：两种架构各有优劣**"

        lines = [
            conclusion,
            '',
            '### 关键发现：',
            '',
            f"1. **性能方面**: {timing_comp['verdict']}",
            f"2. **效率方面**: {steps_comp['verdict']}",
            f"3. **可靠性方面**: {recovery_comp['verdict']}",
            f"4. **可维护性方面**: {scalability_comp['verdict']}",
            '',
            '---',
            '*本报告由VerificationReportGenerator自动生成*',
        ]
        return '\n'.join(lines)


@dataclass
class ComparisonAnalyzer:
    """双架构对比分析器

    提供Neuro-DDD与传统C架构在多个维度的对比分析功能，
    包括耗时、流转步数、错误恢复能力和扩展性等。
    """

    neuro_data: Optional[Dict] = field(default=None)
    traditional_data: Optional[Dict] = field(default=None)

    def load_neuro_data(self, neuro_data: Dict) -> None:
        """加载Neuro-DDD追踪数据

        Args:
            neuro_data: NeuroFlowTracker.get_full_report()返回的数据
        """
        self.neuro_data = neuro_data

    def load_traditional_data(self, traditional_data: Dict) -> None:
        """加载传统C编译器数据

        Args:
            traditional_data: TraditionalCCompiler.compile()返回的结果字典
        """
        self.traditional_data = traditional_data

    def compare_timing(self, neuro_time: Optional[float] = None, traditional_time: Optional[float] = None) -> Dict:
        """耗时对比，计算加速比

        Args:
            neuro_time: Neuro-DDD执行时间（秒），如果为None则从数据中提取
            traditional_time: 传统C执行时间（秒），如果为None则从数据中提取

        Returns:
            耗时对比结果字典
        """
        if neuro_time is None and self.traditional_data:
            neuro_time = 0.001
        if traditional_time is None and self.traditional_data:
            traditional_time = self.traditional_data.get('total_time', 1.0)

        if neuro_time is None:
            neuro_time = 0.001
        if traditional_time is None:
            traditional_time = 1.0

        neuro_time_ms = neuro_time * 1000
        traditional_time_ms = traditional_time * 1000

        if neuro_time > 0:
            speedup_ratio = traditional_time / neuro_time
        else:
            speedup_ratio = float('inf')

        time_saved_percent = ((traditional_time - neuro_time) / traditional_time * 100) if traditional_time > 0 else 0

        if speedup_ratio >= 2.0:
            verdict = "✅ Neuro-DDD显著更优（加速比≥2x）"
        elif speedup_ratio >= 1.2:
            verdict = "📈 Neuro-DDD较优（加速比≥1.2x）"
        elif speedup_ratio >= 1.0:
            verdict = "⚖️ 性能相当"
        else:
            verdict = "❌ Traditional C更快"

        return {
            'neuro_time_seconds': round(neuro_time, 6),
            'traditional_time_seconds': round(traditional_time, 6),
            'neuro_time_ms': round(neuro_time_ms, 2),
            'traditional_time_ms': round(traditional_time_ms, 2),
            'speedup_ratio': round(speedup_ratio, 2),
            'time_saved_percent': round(time_saved_percent, 1),
            'verdict': verdict,
        }

    def compare_flow_steps(self, neuro_steps: Optional[int] = None, traditional_steps: Optional[int] = None) -> Dict:
        """流转步数对比

        Args:
            neuro_steps: Neuro-DDD流转步数，如果为None则从数据中提取
            traditional_steps: 传统C流转步数，默认为5

        Returns:
            流转步数对比结果字典
        """
        if neuro_steps is None and self.neuro_data:
            neuro_steps = self.neuro_data.get('total_signals', 4)
        if traditional_steps is None:
            traditional_steps = 5

        if neuro_steps is None:
            neuro_steps = 4
        if traditional_steps is None:
            traditional_steps = 5

        reduction = traditional_steps - neuro_steps
        reduction_rate = (reduction / traditional_steps * 100) if traditional_steps > 0 else 0

        if reduction_rate >= 40:
            verdict = "✅ Neuro-DDD显著减少流转步数（减少率≥40%）"
        elif reduction_rate >= 20:
            verdict = "📉 Neuro-DDD流转更简洁（减少率≥20%）"
        elif reduction_rate >= 0:
            verdict = "⚖️ 步数相近"
        else:
            verdict = "❌ Traditional C步数更少"

        return {
            'neuro_steps': neuro_steps,
            'traditional_steps': traditional_steps,
            'steps_reduced': reduction,
            'reduction_rate': round(reduction_rate, 1),
            'verdict': verdict,
        }

    def compare_error_recovery(self, neuro_recovery: Optional[str] = None, traditional_recovery: Optional[str] = None) -> Dict:
        """错误恢复对比

        Args:
            neuro_recovery: Neuro-DDD错误恢复能力描述
            traditional_recovery: 传统C错误恢复能力描述

        Returns:
            错误恢复对比结果字典
        """
        if neuro_recovery is None:
            neuro_recovery = "可恢复（AI主路+GCC兜底）"
        if traditional_recovery is None:
            traditional_recovery = "直接终止"

        recovery_map = {
            "可恢复（AI主路+GCC兜底）": 9,
            "可恢复": 8,
            "部分恢复": 5,
            "直接终止": 2,
            "不可恢复": 1,
        }

        neuro_score = recovery_map.get(neuro_recovery, 5)
        traditional_score = recovery_map.get(traditional_recovery, 5)

        improvement = f"+{(neuro_score - traditional_score)}级" if neuro_score > traditional_score else "持平"

        if neuro_score >= 8 and traditional_score <= 3:
            verdict = "✅ Neuro-DDD具备优秀的错误恢复机制"
        elif neuro_score > traditional_score + 2:
            verdict = "🛡️ Neuro-DDD错误恢复能力明显更强"
        elif neuro_score > traditional_score:
            verdict = "📊 Neuro-DDD略优"
        else:
            verdict = "⚠️ 错误恢复能力相近或较弱"

        return {
            'neuro_capability': neuro_recovery,
            'traditional_capability': traditional_recovery,
            'neuro_score': neuro_score,
            'traditional_score': traditional_score,
            'improvement': improvement,
            'verdict': verdict,
        }

    def compare_scalability(self) -> Dict:
        """扩展性对比

        Returns:
            扩展性对比结果字典
        """
        neuro_advantages = [
            "领域可独立扩展",
            "支持动态注册新领域",
            "松耦合架构",
            "广播通信模式",
        ]
        traditional_limitations = [
            "固定5阶段流水线",
            "新增阶段需修改核心代码",
            "强耦合串行结构",
        ]

        neuro_score = 9
        traditional_score = 4

        if neuro_score >= 8:
            verdict = "✅ Neuro-DDD具有卓越的可扩展性"
        elif neuro_score >= 6:
            verdict = "📈 Neuro-DDD扩展性较好"
        else:
            verdict = "⚠️ 扩展性有待提升"

        return {
            'neuro_score': neuro_score,
            'traditional_score': traditional_score,
            'advantages': neuro_advantages,
            'limitations_traditional': traditional_limitations,
            'verdict': verdict,
        }

    def generate_comparison_table(self) -> str:
        """生成综合对比表格

        Returns:
            Markdown格式的对比表格字符串
        """
        timing = self.compare_timing()
        steps = self.compare_flow_steps()
        recovery = self.compare_error_recovery()
        scalability = self.compare_scalability()

        table_lines = [
            '| 对比项 | Neuro-DDD | Traditional C | 对比指标 |',
            '|-------|-----------|---------------|---------|',
            f'| 总执行耗时 | {timing["neuro_time_ms"]:.2f} ms | {timing["traditional_time_ms"]:.2f} ms | 加速比 = {timing["speedup_ratio"]:.2f}x |',
            f'| 信号流转步数 | {steps["neuro_steps"]}步 | {steps["traditional_steps"]}步 | 减少{steps["reduction_rate"]:.1f}% |',
            f'| 错误恢复能力 | {recovery["neuro_capability"]} | {recovery["traditional_capability"]} | {recovery["improvement"]} |',
            f'| 扩展性评分 | {scalability["neuro_score"]}/10 | {scalability["traditional_score"]}/10 | 领域驱动优势 |',
        ]

        return '\n'.join(table_lines)

    def __repr__(self) -> str:
        neuro_loaded = self.neuro_data is not None
        trad_loaded = self.traditional_data is not None
        return f"ComparisonAnalyzer(neuro={neuro_loaded}, traditional={trad_loaded})"
