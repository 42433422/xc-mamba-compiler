"""JNCC 研究评测：静态指标、规模分桶、错误类别。"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


def count_asm_instructions(asm: str) -> int:
    n = 0
    for ln in asm.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("//") or s.startswith("."):
            continue
        if re.match(r"^[a-zA-Z_.][a-zA-Z0-9_.]*:", s):
            continue
        if s.startswith("/*"):
            continue
        n += 1
    return n


def xc_nonblank_lines(xc: str) -> int:
    return sum(1 for ln in xc.splitlines() if ln.strip())


def size_bucket(line_count: int) -> str:
    """按非空行数分桶，便于「十行级 vs 千行级」可扩展性报告。"""
    if line_count <= 10:
        return "micro_le10"
    if line_count <= 50:
        return "small_11_50"
    if line_count <= 120:
        return "medium_51_120"
    if line_count <= 400:
        return "large_121_400"
    if line_count <= 1000:
        return "xlarge_401_1000"
    return "xxlarge_gt1000"


def classify_compiler_outcome(
    *,
    parse_ok: bool,
    pred_asm: str,
    gold_asm: str,
) -> str:
    """
    AI 编译器典型错误/结果分类（用于错误分析与论文式统计）。
    Oracle 是否支持该 XC 单独记在行元数据 oracle_supported，不与此枚举混为一谈。
    """
    if not parse_ok:
        return "E1_parse_fail"
    if not (pred_asm or "").strip():
        return "E2_model_empty_output"
    from xc_asm_validate import assemble_check, basic_asm_sanity

    ok_a, _ = assemble_check(pred_asm)
    ok_s, _ = basic_asm_sanity(pred_asm)
    if not ok_a:
        return "E3_assemble_reject"
    if not ok_s:
        return "E4_sanity_reject"
    if not (gold_asm or "").strip():
        return "ok_assemble_no_gold_compare"
    from compiler.jncc_asm_norm import normalized_asm_diff

    if normalized_asm_diff(pred_asm, gold_asm).get("equal_normalized"):
        return "ok_match_oracle_asm"
    return "E6_mismatch_normalized_vs_dataset_gold"


def aggregate_buckets(rows: list[dict[str, Any]]) -> Dict[str, Any]:
    """rows 每项含 bucket, category, assemble_ok, match_gold, t_gen, t_oracle, n_instr_pred, n_instr_gold"""
    from collections import defaultdict

    by_b: Dict[str, list] = defaultdict(list)
    for r in rows:
        by_b[r.get("bucket", "_")].append(r)
    out = {}
    for b, lst in sorted(by_b.items()):
        n = len(lst)
        ap = sum(1 for x in lst if x.get("assemble_ok"))
        mg = sum(1 for x in lst if x.get("match_gold"))
        out[b] = {
            "n": n,
            "assemble_pass_rate": ap / n if n else 0.0,
            "norm_match_rate": mg / n if n else 0.0,
            "mean_gen_sec": sum(x.get("t_gen", 0) for x in lst) / n if n else 0.0,
            "mean_oracle_sec": sum(x.get("t_oracle", 0) for x in lst) / n if n else 0.0,
            "mean_size_ratio": _mean_ratio(lst),
        }
    return out


def _mean_ratio(lst: list) -> float:
    ratios = []
    for x in lst:
        g = x.get("n_instr_gold", 0) or 0
        p = x.get("n_instr_pred", 0) or 0
        if g > 0 and x.get("assemble_ok"):
            ratios.append(p / g)
    return sum(ratios) / len(ratios) if ratios else 0.0


def error_histogram(categories: list[str]) -> Dict[str, int]:
    from collections import Counter

    return dict(Counter(categories))
