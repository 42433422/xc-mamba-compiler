#!/usr/bin/env python3
"""
Generate pred_asm with a local causal-lm checkpoint (Mamba/JNCC or any HF CausalLM).

This does NOT run qemu. It only generates assembly text and writes a JSONL file:
  - keeps original fields from input jsonl
  - adds "pred_asm"
  - records generation time per row

Example:
  python tools/jncc_generate_pred_asm.py \
    --jsonl dataset/xc_asm_test.jsonl \
    --model models/JNCC/final \
    --out reports/pred_asm_model.jsonl \
    --limit 5 \
    --no_cuda
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.jncc_model_infer import load_causal_lm_bundle  # noqa: E402
from compiler.xc_asm_prompt import build_prompt, resolve_prompt_mode  # noqa: E402
from xc_asm_validate import assemble_check, basic_asm_sanity  # noqa: E402


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


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate pred_asm for Linux runtime validation.")
    ap.add_argument("--jsonl", type=str, required=True)
    ap.add_argument("--model", type=str, required=True)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--max_new_tokens", type=int, default=2048)
    ap.add_argument("--no_cuda", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--temperatures", type=str, default="0.0,0.2,0.4")
    ap.add_argument(
        "--prompt_mode",
        choices=["short", "teacher"],
        default="",
        help="空=读环境变量 XC_ASM_PROMPT_MODE（默认 short）；teacher=强化 Oracle/RVV/寄存器/流水",
    )
    return ap.parse_args()


def parse_csv_floats(s: str) -> Tuple[float, ...]:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return tuple(float(x) for x in parts) if parts else (0.0,)


def truncate_first_main_block(asm: str) -> str:
    m = re.search(r"\.size[ \t]+main[ \t]*,[^\n]*\n", asm)
    if not m:
        return asm
    start = asm.find(".file")
    if start == -1:
        start = 0
    return asm[start : m.end()]


def generate_with_retries(
    bundle: dict,
    xc: str,
    *,
    hierarchical: bool,
    max_new_tokens: int,
    attempts: int,
    temperatures: Tuple[float, ...],
    prompt_mode: str,
) -> Tuple[str, float, List[Dict[str, Any]], bool]:
    import torch

    tok = bundle["tok"]
    model = bundle["model"]
    device = bundle["device"]
    pm = resolve_prompt_mode(prompt_mode if prompt_mode in ("short", "teacher") else None)
    prompt = build_prompt(xc, hierarchical, mode=pm)
    inputs = tok(prompt, return_tensors="pt").to(device)

    temps = list(temperatures)
    while len(temps) < attempts:
        temps.append(temps[-1])

    details: List[Dict[str, Any]] = []
    t0 = time.perf_counter()
    best_text = ""
    for i in range(attempts):
        t = temps[i]
        do_sample = t > 0
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=t if do_sample else None,
                pad_token_id=tok.eos_token_id,
            )
        gen = tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True).strip()
        cleaned = truncate_first_main_block(gen)
        ok_a, msg_a = assemble_check(cleaned)
        ok_s, msg_s = basic_asm_sanity(cleaned)
        details.append(
            {
                "attempt": i + 1,
                "temperature": t,
                "assemble_ok": bool(ok_a),
                "sanity_ok": bool(ok_s),
                "assemble_msg": msg_a[:200],
                "sanity_msg": msg_s,
                "pred_len": len(cleaned),
            }
        )
        best_text = cleaned
        if ok_a and ok_s:
            return cleaned, time.perf_counter() - t0, details, True

    return best_text, time.perf_counter() - t0, details, False


def main() -> int:
    args = parse_args()

    in_path = Path(args.jsonl)
    if not in_path.is_file():
        print(f"Missing jsonl: {in_path}")
        return 2

    out_path = Path(args.out) if args.out else (ROOT / "reports" / f"pred_asm_{Path(args.model).name}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(in_path, args.limit)
    if not rows:
        print("No rows.")
        return 2

    # Load model once.
    bundle = load_causal_lm_bundle(args.model, no_cuda=args.no_cuda)
    temps = parse_csv_floats(args.temperatures)

    per_row_times: List[float] = []
    n_valid = 0
    with open(out_path, "w", encoding="utf-8") as wf:
        for i, row in enumerate(rows, start=1):
            xc = row.get("xc_source") or ""
            rid = row.get("id") or f"row_{i}"
            if not xc.strip():
                row_out = dict(row)
                row_out["pred_asm"] = ""
                row_out["t_gen_sec"] = 0.0
                row_out["pred_generated"] = False
                wf.write(json.dumps(row_out, ensure_ascii=False) + "\n")
                continue

            pred_asm, t_gen, attempt_info, valid =             generate_with_retries(
                bundle,
                xc,
                hierarchical=args.hierarchical,
                max_new_tokens=args.max_new_tokens,
                attempts=args.attempts,
                temperatures=temps,
                prompt_mode=args.prompt_mode,
            )
            per_row_times.append(t_gen)
            if valid:
                n_valid += 1
            row_out = dict(row)
            row_out["pred_asm"] = pred_asm
            row_out["t_gen_sec"] = t_gen
            row_out["pred_generated"] = bool(pred_asm)
            row_out["pred_asm_validated"] = valid
            row_out["pred_attempts"] = attempt_info
            wf.write(json.dumps(row_out, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(rows)}] {rid} t_gen={t_gen:.2f}s valid={valid} pred_len={len(pred_asm)}")

    if per_row_times:
        print("\n=== Generation Summary ===")
        print(
            f"rows={len(per_row_times)} valid={n_valid} "
            f"mean_t_gen={statistics.mean(per_row_times):.4f}s "
            f"median_t_gen={statistics.median(per_row_times):.4f}s"
        )

    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

