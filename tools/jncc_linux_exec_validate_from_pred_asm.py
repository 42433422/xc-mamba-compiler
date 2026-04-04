#!/usr/bin/env python3
"""
Run qemu-riscv64 execution validation for a JSONL that already contains pred_asm.

Input JSONL should have:
  - asm_riscv64: oracle gold assembly (used as runtime baseline)
  - pred_asm: target assembly to validate

Output:
  - reports/linux_exec_validate_from_pred_<backend>.json

Important:
  This script only performs toolchain compile + qemu execution via xc_asm_validate.try_compile_and_qemu_exit_code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.jncc_asm_norm import normalized_asm_diff  # noqa: E402
from xc_asm_validate import get_toolchain_info, try_compile_and_qemu_exit_code  # noqa: E402


def load_jsonl(path: Path, limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit > 0 and len(rows) >= limit:
                break
    return rows


def extract_first_main_block(asm: str) -> str:
    """
    Best-effort cleanup for model outputs that may include duplicated/truncated tail.

    Heuristic:
    - keep from the first '.file' (if present)
    - up to (and including) the first '.size main' line after that
    """
    import re

    if not asm.strip():
        return asm

    s = asm
    start = s.find(".file")
    if start == -1:
        start = 0

    # Match: ".size <spaces/tabs> main , ..." where whitespace is flexible.
    # Examples observed in repo outputs:
    #   .size main, .-main
    #   .size\tmain,.-main
    m = re.search(r"\.size[ \t]+main[ \t]*,[^\n]*\n", s[start:])
    if not m:
        return s
    end = start + m.end()
    return s[start:end]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate runtime equivalence (qemu) from pred_asm JSONL.")
    ap.add_argument("--jsonl", type=str, required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--backend_label", type=str, default="model")
    ap.add_argument("--timeout_sec", type=float, default=5.0)
    ap.add_argument(
        "--proximity",
        action="store_true",
        help="附加与 Oracle 的规范化汇编对比（行数、是否逐行相等）；见 dataset/evaluation_spec.json 指标 B",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    info = get_toolchain_info()
    if not info.get("qemu") or not info.get("gcc"):
        print("Missing qemu or riscv64 gcc in this environment.")
        print(info)
        return 2

    in_path = Path(args.jsonl)
    if not in_path.is_file():
        print(f"Missing jsonl: {in_path}")
        return 2

    rows = load_jsonl(in_path, args.limit)
    if not rows:
        print("No rows.")
        return 2

    out_path = Path(args.out) if args.out else (ROOT / "reports" / f"linux_exec_validate_from_pred_{args.backend_label}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    details: List[Dict[str, Any]] = []
    match = 0
    oracle_ok = 0
    target_ok = 0
    norm_match = 0
    spec_path = ROOT / "dataset" / "evaluation_spec.json"

    for i, row in enumerate(rows, start=1):
        rid = row.get("id") or f"row_{i}"
        gold = row.get("asm_riscv64") or ""
        pred_raw = row.get("pred_asm") or ""
        pred = extract_first_main_block(pred_raw)

        gold_rc, gold_msg = try_compile_and_qemu_exit_code(gold)
        pred_rc, pred_msg = try_compile_and_qemu_exit_code(pred)

        gold_ok = gold_rc is not None
        pred_ok = pred_rc is not None
        if gold_ok:
            oracle_ok += 1
        if pred_ok:
            target_ok += 1

        ok = bool(gold_ok and pred_ok and gold_rc == pred_rc)
        if ok:
            match += 1

        prox: Dict[str, Any] = {}
        if args.proximity:
            d = normalized_asm_diff(pred, gold)
            prox = {
                "normalized_asm_equal": bool(d.get("equal_normalized")),
                "norm_line_count_pred": d.get("line_count_pred"),
                "norm_line_count_gold": d.get("line_count_gold"),
            }
            if prox.get("normalized_asm_equal"):
                norm_match += 1

        rec: Dict[str, Any] = {
            "id": rid,
            "oracle_qemu_exit_code": gold_rc,
            "pred_qemu_exit_code": pred_rc,
            "pred_used_postprocess": pred != pred_raw,
            "oracle_ok": gold_ok,
            "pred_ok": pred_ok,
            "runtime_match_oracle": ok,
            "oracle_msg": gold_msg[:2000],
            "pred_msg": pred_msg[:2000],
        }
        if prox:
            rec["oracle_proximity"] = prox
        details.append(rec)
        print(f"[{i}/{len(rows)}] {rid} oracle={gold_rc} pred={pred_rc} match={ok}")

    denom = len(rows)
    summary: Dict[str, Any] = {
        "dataset": str(in_path),
        "rows_total": len(rows),
        "backend_label": args.backend_label,
        "evaluation_spec": str(spec_path) if spec_path.is_file() else "",
        "oracle_runtime_ok_rate": oracle_ok / denom,
        "pred_runtime_ok_rate": target_ok / denom,
        "runtime_match_rate": match / denom,
        "toolchain": {"gcc": info.get("gcc"), "qemu": info.get("qemu")},
    }
    if args.proximity:
        summary["normalized_asm_match_rate"] = norm_match / denom

    out_path.write_text(json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nReport written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

