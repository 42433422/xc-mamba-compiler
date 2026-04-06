#!/usr/bin/env python3
"""
Generate pred_asm using generate_asm_attempts (with assemble_check gating).

This is more robust than greedy-only decoding because it retries with different
temperatures until the generated assembly passes repository syntax checks.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.jncc_model_infer import generate_asm_attempts  # noqa: E402


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


def parse_csv_floats(s: str) -> Tuple[float, ...]:
    s = s.strip()
    if not s:
        return (0.0,)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return tuple(float(p) for p in parts)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate pred_asm with assemble_check gating.")
    ap.add_argument("--jsonl", type=str, required=True)
    ap.add_argument("--model", type=str, required=True)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--max_new_tokens", type=int, default=1024)
    ap.add_argument("--attempts", type=int, default=2)
    ap.add_argument("--temperatures", type=str, default="0.0,0.2")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no_cuda", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    in_path = Path(args.jsonl)
    if not in_path.is_file():
        print(f"Missing jsonl: {in_path}")
        return 2

    out_path = Path(args.out) if args.out else (ROOT / "reports" / f"pred_asm_model_attempts.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(in_path, args.limit)
    if not rows:
        print("No rows.")
        return 2

    temps = parse_csv_floats(args.temperatures)
    per_row_times: List[float] = []

    with open(out_path, "w", encoding="utf-8") as wf:
        for i, row in enumerate(rows, start=1):
            xc = row.get("xc_source") or ""
            rid = row.get("id") or f"row_{i}"
            if not xc.strip():
                row_out = dict(row)
                row_out["pred_asm"] = ""
                row_out["pred_generated"] = False
                wf.write(json.dumps(row_out, ensure_ascii=False) + "\n")
                continue

            pred_asm, details = generate_asm_attempts(
                xc,
                args.model,
                hierarchical=args.hierarchical,
                max_new_tokens=args.max_new_tokens,
                attempts=args.attempts,
                temperatures=temps,
                seed=args.seed,
                no_cuda=args.no_cuda,
            )

            row_out = dict(row)
            row_out["pred_asm"] = pred_asm or ""
            row_out["pred_generated"] = bool(pred_asm)
            row_out["pred_attempts"] = details
            wf.write(json.dumps(row_out, ensure_ascii=False) + "\n")

            ok_a = bool(pred_asm)  # generate_asm_attempts returns None when assemble_check fails for all attempts
            print(f"[{i}/{len(rows)}] {rid} pred_generated={ok_a} attempts={len(details)}")

            # We don't get per-try timings from generate_asm_attempts; keep summary as empty.

    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

