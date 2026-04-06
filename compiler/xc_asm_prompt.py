"""
XC→RISC-V 汇编：推理与训练共用的 prompt，避免分布漂移。

模式:
  short   — 一句话指令（与历史行为兼容，默认）。
  teacher — 强化：ABI/Oracle 风格、寄存器分配、条件使用 RVV 与流水意图；需配合 SFT 才能逼近高一致率。

说明: 「99.9% 退出码一致 / 生成速度追上 Oracle」依赖足够数据与训练算力；本模块提供对齐目标与可训练模板，不保证数值本身。
"""

from __future__ import annotations

import os
from typing import Literal

PromptMode = Literal["short", "teacher"]

_TEACHER_VARIANTS = (
    # 中文主模板
    """你是 RISC-V64（GNU as）汇编写手。只输出汇编，不要解释。

硬性要求：
- Linux lp64d ABI：.text、.globl main、标准 prologue/epilogue；返回值在 a0（32 位语义用 addw/subw/mulw 等 W 系指令，符号扩展按 int）。
- 尽量贴近参考编译器 Oracle：少无关栈槽、少重复 load；临时量优先 t0–t6，帧指针用 s0，保存/恢复 ra 与 s0。
- 比较与分支：与常见 Oracle 一致（如相等可用 subw + seqz、slt/sltu、beqz/bnez）；避免杜撰助记符。
- 寄存器分配：同一基本块内复用临时寄存器；跨调用遵守调用约定。
- RVV：仅当题目明确写「向量化/RVV/向量/内核」或给出连续内存与长度时才使用；写清 vsetvli（sew、lmul、ta/ma），否则只用标量指令。
- 软件流水线：仅当输入结构表现为显式循环/多迭代时再考虑交错 load 与运算；否则以正确、可读为先。

输出：从 .file 或 .text 开始到 .size main 为止的完整汇编。""",
    # 中英混排，防过拟合单一措辞
    """RISC-V64 GNU assembly only, no commentary.

Goals: match Oracle-style lowering (frame, spills, compare patterns). Use W-arithmetic for 32-bit int semantics. Prefer t0–t6 for temps; keep ra/s0 consistent.

RVV: only if the XC/spec explicitly requests vectors or a kernel with pointer+length; otherwise stay scalar. If RVV: vsetvli with explicit sew/lmul and ta/ma.

Software pipelining: only when the program structure is an explicit loop; otherwise prioritize correctness.

Emit a single complete main routine (.globl main … .size main).""",
    # 分层输入提示
    """[Hierarchical] 阅读 <<<PROGRAM>>> / <<<STMT_n>>> 结构，再生成与 Oracle 同风格的 RISC-V64 GNU 汇编；只输出汇编。

要点：ABI 正确；int 用 W 指令族；分支比较模式稳定；寄存器紧凑分配；仅在明确要求时使用 RVV 与流水化。""",
)


def prepare_input_body(xc_source: str, hierarchical: bool) -> str:
    inp = xc_source.strip()
    if not hierarchical:
        return inp
    lines = [ln for ln in inp.splitlines() if ln.strip()]
    hier = ["<<<PROGRAM>>>"] + [f"<<<STMT_{i}>>>{ln}" for i, ln in enumerate(lines)]
    return "\n".join(hier)


def instruction_for_mode(mode: PromptMode, template_id: int) -> str:
    if mode == "short":
        pool = (
            "将 XC 翻译为 RISC-V64 GNU 汇编，只输出汇编，不要解释。",
            "Translate the following XC program to RISC-V64 (GNU as) assembly only.",
            "[Hierarchical] 使用 <<<PROGRAM>>>/<<<STMT_n>>> 结构理解代码，输出汇编：",
        )
        return pool[template_id % len(pool)]
    return _TEACHER_VARIANTS[template_id % len(_TEACHER_VARIANTS)]


def format_xc_asm_prompt(input_body: str, mode: PromptMode, template_id: int = 0) -> str:
    instr = instruction_for_mode(mode, template_id)
    return f"{instr}\n\n### 输入\n{input_body}\n\n### 汇编\n"


def resolve_prompt_mode(explicit: PromptMode | None) -> PromptMode:
    if explicit is not None:
        return explicit
    v = (os.environ.get("XC_ASM_PROMPT_MODE") or "short").strip().lower()
    if v in ("teacher", "full", "distill"):
        return "teacher"
    return "short"


def build_training_input_body(row: dict, hierarchical: bool) -> str:
    """训练样本输入侧：分层字段优先用 hierarchical_input，与 JSONL 一致。"""
    if hierarchical:
        h = (row.get("hierarchical_input") or "").strip()
        if h:
            return h
    return prepare_input_body(row.get("xc_source") or "", hierarchical)


def build_prompt(
    xc_source: str,
    hierarchical: bool,
    *,
    mode: PromptMode | None = None,
    template_id: int = 0,
) -> str:
    """推理入口：mode 默认读环境变量 XC_ASM_PROMPT_MODE（short|teacher）。"""
    m = resolve_prompt_mode(mode)
    body = prepare_input_body(xc_source, hierarchical)
    return format_xc_asm_prompt(body, m, template_id)
