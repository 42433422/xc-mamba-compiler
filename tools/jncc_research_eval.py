#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JNCC 研究向评估（定量 / 消融 / 规模 / 错误 / Oracle 对比）。

说明：「基准集」默认使用仓库内 xc_asm_{val,test}.jsonl（合成+Oracle 标注），
并非 SPEC CPU / LLVM 等工业标准套件；论文中应如实写明数据来源与局限。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.jncc_asm_norm import normalized_asm_diff
from compiler.jncc_eval_metrics import (
    aggregate_buckets,
    classify_compiler_outcome,
    count_asm_instructions,
    error_histogram,
    size_bucket,
    xc_nonblank_lines,
)
from compiler.jncc_model_infer import generate_asm_greedy_timed, load_causal_lm_bundle
from compiler.jncc_pipeline import _parse_stage
from xc_asm_oracle import compile_xc_to_asm_riscv64_with_reason
from xc_asm_validate import assemble_check, basic_asm_sanity


def load_jsonl(path: Path, limit: int) -> List[dict]:
    rows: List[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    return rows


def _row_metrics(
    row: dict,
    bundle: dict,
    *,
    hierarchical: bool,
    max_new_tokens: int,
) -> dict[str, Any]:
    xc = row.get("xc_source") or ""
    gold = (row.get("asm_riscv64") or "").strip()
    ps = _parse_stage(xc)
    t0 = time.perf_counter()
    ores = compile_xc_to_asm_riscv64_with_reason(xc)
    t_oracle = time.perf_counter() - t0
    pred, t_gen = generate_asm_greedy_timed(
        bundle, xc, hierarchical=hierarchical, max_new_tokens=max_new_tokens
    )
    cat = classify_compiler_outcome(
        parse_ok=bool(ps.get("ok")),
        pred_asm=pred,
        gold_asm=gold,
    )
    ok_a, _ = assemble_check(pred)
    ok_s, _ = basic_asm_sanity(pred)
    match = bool(gold) and normalized_asm_diff(pred, gold).get("equal_normalized", False)
    nb = xc_nonblank_lines(xc)
    return {
        "id": row.get("id"),
        "bucket": size_bucket(nb),
        "xc_lines_nonblank": nb,
        "category": cat,
        "oracle_supported": bool(ores.get("ok")),
        "oracle_unsupported_reason": ores.get("unsupported_reason"),
        "assemble_ok": ok_a and ok_s,
        "match_gold": match,
        "t_gen": t_gen,
        "t_oracle": t_oracle,
        "n_instr_pred": count_asm_instructions(pred),
        "n_instr_gold": count_asm_instructions(gold),
    }


def eval_one_model(
    jsonl_path: Path,
    model_path: str,
    *,
    limit: int,
    hierarchical: bool,
    max_new_tokens: int,
    no_cuda: bool,
    model_label: str,
) -> Dict[str, Any]:
    rows = load_jsonl(jsonl_path, limit)
    bundle = load_causal_lm_bundle(model_path, no_cuda=no_cuda)
    try:
        out_rows: List[dict[str, Any]] = []
        for row in rows:
            out_rows.append(
                _row_metrics(
                    row,
                    bundle,
                    hierarchical=hierarchical,
                    max_new_tokens=max_new_tokens,
                )
            )
    finally:
        del bundle
        try:
            import gc

            import torch

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    n = len(out_rows)
    if n == 0:
        return {
            "per_row": [],
            "summary": {
                "model_label": model_label,
                "model_path": model_path,
                "n_rows": 0,
                "quantitative": {},
                "by_scale_bucket": {},
                "error_taxonomy": {},
                "oracle_vs_ai_note": "empty suite",
            },
        }
    supported = [r for r in out_rows if r["oracle_supported"]]
    sup_n = len(supported)
    ap = sum(1 for r in out_rows if r["assemble_ok"])
    mg = sum(1 for r in out_rows if r["match_gold"])
    ap_s = sum(1 for r in supported if r["assemble_ok"])
    mg_s = sum(1 for r in supported if r["match_gold"])
    gens = [r["t_gen"] for r in out_rows]
    oracles = [r["t_oracle"] for r in out_rows]

    ratios = []
    for r in out_rows:
        g = r["n_instr_gold"]
        p = r["n_instr_pred"]
        if g > 0 and r["assemble_ok"]:
            ratios.append(p / g)

    report = {
        "model_label": model_label,
        "model_path": model_path,
        "n_rows": n,
        "quantitative": {
            "assemble_pass_rate_all": ap / n if n else 0.0,
            "norm_match_gold_rate_all": mg / n if n else 0.0,
            "on_oracle_supported_subset_n": sup_n,
            "assemble_pass_rate_on_supported": ap_s / sup_n if sup_n else 0.0,
            "norm_match_gold_rate_on_supported": mg_s / sup_n if sup_n else 0.0,
            "mean_ai_gen_sec": statistics.mean(gens) if gens else 0.0,
            "median_ai_gen_sec": statistics.median(gens) if gens else 0.0,
            "mean_oracle_sec": statistics.mean(oracles) if oracles else 0.0,
            "median_oracle_sec": statistics.median(oracles) if oracles else 0.0,
            "mean_size_ratio_pred_over_gold_when_assembled": statistics.mean(ratios) if ratios else 0.0,
            "median_size_ratio_pred_over_gold_when_assembled": statistics.median(ratios) if ratios else 0.0,
        },
        "by_scale_bucket": aggregate_buckets(out_rows),
        "error_taxonomy": error_histogram([r["category"] for r in out_rows]),
        "oracle_vs_ai_note": (
            "规则 Oracle 在 supported 子集上为金标准；AI 指标为 assemble 通过与规范化后与数据集中 asm_riscv64 一致率。"
        ),
    }
    return {"per_row": out_rows, "summary": report}


def main() -> int:
    ap = argparse.ArgumentParser(description="JNCC research evaluation suite")
    ap.add_argument("--jsonl", type=str, default=str(ROOT / "dataset" / "xc_asm_val.jsonl"))
    ap.add_argument("--model", type=str, required=True, help="Mamba/JNCC 或任意 HF CausalLM 目录")
    ap.add_argument("--transformer_model", type=str, default="", help="可选：第二个模型路径，做 Mamba vs Transformer 消融")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--max_new_tokens", type=int, default=2048)
    ap.add_argument("--no_cuda", action="store_true")
    ap.add_argument("--include_rows", action="store_true", help="报告中附带每条样本的指标（体积大）")
    ap.add_argument("--out", type=str, default="", help="JSON 报告路径；默认打印 stdout")
    args = ap.parse_args()

    path = Path(args.jsonl)
    if not path.is_file():
        print(f"missing {path}", file=sys.stderr)
        return 1

    full: Dict[str, Any] = {
        "benchmark_scope": "xc_asm JSONL（仓库内合成语料 + Oracle 汇编标签），非 SPEC/LLVM 工业基准",
        "suite": str(path),
    }

    pr = eval_one_model(
        path,
        args.model,
        limit=args.limit,
        hierarchical=args.hierarchical,
        max_new_tokens=args.max_new_tokens,
        no_cuda=args.no_cuda,
        model_label="mamba_or_primary",
    )
    full["mamba_or_primary"] = pr["summary"]
    if args.include_rows:
        full["mamba_or_primary"]["per_row"] = pr["per_row"]

    if args.transformer_model.strip():
        tr_path = Path(args.transformer_model)
        if not tr_path.is_dir():
            print(f"missing transformer model dir {tr_path}", file=sys.stderr)
            return 1
        tr = eval_one_model(
            path,
            str(tr_path),
            limit=args.limit,
            hierarchical=args.hierarchical,
            max_new_tokens=args.max_new_tokens,
            no_cuda=args.no_cuda,
            model_label="transformer_ablation",
        )
        mq = full["mamba_or_primary"]["quantitative"]
        tq = tr["summary"]["quantitative"]
        full["ablation_transformer_vs_primary"] = {
            "transformer_path": str(tr_path),
            "transformer_summary": tq,
            "primary_summary": mq,
            "delta_assemble_pass_on_supported": tq["assemble_pass_rate_on_supported"]
            - mq["assemble_pass_rate_on_supported"],
            "delta_match_gold_on_supported": tq["norm_match_gold_rate_on_supported"]
            - mq["norm_match_gold_rate_on_supported"],
            "delta_mean_gen_sec": tq["mean_ai_gen_sec"] - mq["mean_ai_gen_sec"],
        }
        if args.include_rows:
            full["ablation_transformer_vs_primary"]["per_row"] = tr["per_row"]

    text = json.dumps(full, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text[:200000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
