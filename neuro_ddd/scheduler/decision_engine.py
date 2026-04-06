import time
from typing import Dict, List, Optional, Any

from ..core.types import SchedulingDecision


class BrainStateSimulator:
    """脑状态模拟器 - 模拟不同脑状态下的调度偏好

    该类模拟大脑在不同工作状态下的AI信任度和调度倾向，
    为决策引擎提供动态的权重调整依据。

    Attributes:
        current_state: 当前脑状态名称
        states: 各状态的AI偏好权重映射
    """

    def __init__(self, initial_state: str = "正常") -> None:
        """初始化脑状态模拟器

        Args:
            initial_state: 初始脑状态，默认为"正常"
        """
        self.current_state: str = initial_state
        self.states: Dict[str, float] = {
            "清醒": 1.0,
            "正常": 0.8,
            "疲劳": 0.5,
            "高压": 0.3,
        }

    def set_state(self, state_name: str) -> None:
        """设置当前脑状态

        Args:
            state_name: 目标状态名称（清醒/正常/疲劳/高压）

        Raises:
            ValueError: 如果状态名称不在预定义状态中
        """
        if state_name not in self.states:
            raise ValueError(
                f"无效的脑状态 '{state_name}'，可用状态: {list(self.states.keys())}"
            )
        self.current_state = state_name

    def get_state(self) -> str:
        """获取当前脑状态

        Returns:
            当前脑状态名称
        """
        return self.current_state

    def get_ai_bias(self) -> float:
        """获取当前AI偏好权重

        Returns:
            当前状态下AI编译路径的偏好权重（0.0-1.0）
            值越高表示越倾向于使用AI主路编译
        """
        return self.states.get(self.current_state, 0.8)

    def get_available_states(self) -> List[str]:
        """获取所有可用的脑状态列表

        Returns:
            可用脑状态名称列表
        """
        return list(self.states.keys())


class DecisionEngine:
    """动态调度决策引擎 - Neuro-DDD架构的核心调控单元

    该引擎基于验证结果和脑状态模拟器输出，
    动态决定使用AI主路编译还是GCC兜底编译。
    实现了Neuro-DDD架构中的智能调度决策逻辑。

    Attributes:
        brain_state: 脑状态模拟器引用
        decision_history: 决策历史记录列表
        fallback_compiler: 可选的TraditionalCCompiler引用（用于GCC兜底）
    """

    def __init__(
        self,
        brain_state: Optional[BrainStateSimulator] = None,
        fallback_compiler: Optional[Any] = None,
    ) -> None:
        """初始化决策引擎

        Args:
            brain_state: 脑状态模拟器实例，如果为None则自动创建新实例
            fallback_compiler: GCC兜底编译器引用，用于异常情况下的回退编译
        """
        self.brain_state: BrainStateSimulator = (
            brain_state if brain_state is not None else BrainStateSimulator()
        )
        self.decision_history: List[Dict[str, Any]] = []
        self.fallback_compiler: Optional[Any] = fallback_compiler

    def make_decision(
        self, verification_result: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行核心调度决策

        根据验证结果和当前脑状态，决定采用AI主路编译还是GCC兜底编译。
        决策过程会考虑脑状态加权影响，并在疲劳/高压状态下更倾向于保守策略。

        Args:
            verification_result: 验证结果字符串（"正常"/"异常"）
            context: 可选的环境上下文信息字典

        Returns:
            包含完整决策信息的字典，格式如下：
            {
                "decision": SchedulingDecision枚举值,
                "reason": 决策原因描述,
                "verification_result": 输入的验证结果,
                "brain_state": 当前脑状态,
                "timestamp": 决策时间戳,
                "used_fallback": 是否使用了兜底编译器,
                "fallback_result": 兜底编译器的返回结果（如适用）
            }
        """
        current_brain_state = self.brain_state.get_state()
        ai_bias = self.brain_state.get_ai_bias()
        timestamp = time.time()

        decision_record: Dict[str, Any] = {
            "verification_result": verification_result,
            "brain_state": current_brain_state,
            "ai_bias": ai_bias,
            "timestamp": timestamp,
            "context": context or {},
        }

        used_fallback: bool = False
        fallback_result: Optional[Any] = None

        if verification_result == "正常":
            if ai_bias >= 0.7:
                decision = SchedulingDecision.AI_MAIN
                reason = f"验证通过，脑状态为'{current_brain_state}'(AI权重:{ai_bias})，选择AI主路编译"
            else:
                decision = SchedulingDecision.GCC_FALLBACK
                reason = f"验证通过但脑状态为'{current_brain_state}'(AI权重:{ai_bias}过低)，保守策略启用GCC兜底"
                used_fallback = True
                fallback_result = self._invoke_fallback_compiler(context)
        elif verification_result == "异常":
            decision = SchedulingDecision.GCC_FALLBACK
            reason = f"验证异常检测到问题，强制启用GCC兜底编译（脑状态:'{current_brain_state}', AI权重:{ai_bias}）"
            used_fallback = True
            fallback_result = self._invoke_fallback_compiler(context)
        else:
            decision = SchedulingDecision.GCC_FALLBACK
            reason = f"未知验证结果'{verification_result}'，安全起见启用GCC兜底编译"
            used_fallback = True
            fallback_result = self._invoke_fallback_compiler(context)

        decision_record.update(
            {
                "decision": decision,
                "reason": reason,
                "used_fallback": used_fallback,
                "fallback_result": fallback_result,
            }
        )

        self.decision_history.append(decision_record.copy())
        return decision_record

    def _invoke_fallback_compiler(
        self, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """调用兜底编译器执行GCC编译

        Args:
            context: 编译上下文信息

        Returns:
            兜底编译器的执行结果，如果没有配置则返回None
        """
        if self.fallback_compiler is None:
            return None

        try:
            if hasattr(self.fallback_compiler, "compile"):
                return self.fallback_compiler.compile(context)
            elif callable(self.fallback_compiler):
                return self.fallback_compiler(context)
            else:
                return None
        except Exception:
            return None

    def get_decision_history(self) -> List[Dict[str, Any]]:
        """获取所有决策历史记录

        Returns:
            决策历史记录列表，每条记录包含完整的决策信息
        """
        return self.decision_history.copy()

    def set_fallback_compiler(self, compiler: Any) -> None:
        """设置GCC兜底编译器引用

        Args:
            compiler: 兜底编译器对象或可调用对象
        """
        self.fallback_compiler = compiler

    def clear_history(self) -> None:
        """清空所有决策历史记录"""
        self.decision_history.clear()
