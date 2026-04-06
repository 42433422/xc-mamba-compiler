#!/usr/bin/env python3
"""
Linux runtime validation for JNCC outputs.

What this does:
1) Loads XC samples from a JSONL dataset.
2) Compiles and runs Oracle assembly under qemu-riscv64 as runtime baseline.
3) Compiles and runs a target backend (oracle/model/hybrid/ir).
4) Compares runtime exit codes (target vs Oracle baseline).
5) Writes a structured JSON report under reports/.

Example:
  python tools/jncc_linux_exec_validate.py \
      --jsonl dataset/xc_asm_test.jsonl \
      --backend model \
      --model models/JNCC/final \
      --limit 20
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.jncc_pipeline import run_compile  # noqa: E402
from xc_asm_validate import get_toolchain_info  # noqa: E402


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _qemu_exit(report: Dict[str, Any]) -> int | None:
    q = report.get("stages", {}).get("qemu", {})
    v = q.get("exit_code")
    return int(v) if isinstance(v, int) else None


def _assemble_ok(report: Dict[str, Any]) -> bool:
    return bool(report.get("stages", {}).get("assemble", {}).get("assemble_check", {}).get("ok", False))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate Linux runtime equivalence with qemu-riscv64.")
    ap.add_argument("--jsonl", type=str, default=str(ROOT / "dataset" / "xc_asm_test.jsonl"))
    ap.add_argument("--backend", choices=["oracle", "model", "hybrid", "ir"], default="model")
    ap.add_argument("--model", type=str, default="", help="Required for model/hybrid backend.")
    ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--attempts", type=int, default=4)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no_cuda", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 means use all rows.")
    ap.add_argument(
        "--out",
        type=str,
        default="",
        help="Output JSON path. Default: reports/linux_exec_validate_<backend>.json",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    info = get_toolchain_info()
    if not info.get("gcc") or not info.get("qemu"):
        print("Missing Linux toolchain. Need riscv64 gcc and qemu-riscv64.")
        print("Install example (Debian/Ubuntu): sudo apt install gcc-riscv64-linux-gnu qemu-user")
        print(f"Detected: gcc={info.get('gcc')} qemu={info.get('qemu')}")
        return 2

    if args.backend in ("model", "hybrid") and not args.model:
        print("--model is required for backend=model/hybrid")
        return 2

    dataset = Path(args.jsonl)
    if not dataset.is_file():
        print(f"Dataset not found: {dataset}")
        return 2

    rows = load_jsonl(dataset)
    if args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        print("No rows to validate.")
        return 2

    print(f"[validate] rows={len(rows)} backend={args.backend} dataset={dataset}")

    details: List[Dict[str, Any]] = []
    n = len(rows)
    oracle_runtime_ok = 0
    target_runtime_ok = 0
    runtime_match = 0
    skipped = 0
    target_asm_ok = 0
    total_target_sec = 0.0

    for i, row in enumerate(rows, start=1):
        xc = row.get("xc_source") or ""
        rid = row.get("id") or f"row_{i}"
        if not xc.strip():
            skipped += 1
            details.append({"id": rid, "status": "skip_empty_xc"})
            continue

        # Oracle runtime baseline.
        oracle_report = run_compile(
            xc,
            backend="oracle",
            run_qemu=True,
            no_cuda=True,
        )
        oracle_qemu_exit = _qemu_exit(oracle_report)
        oracle_ok = oracle_qemu_exit is not None
        if oracle_ok:
            oracle_runtime_ok += 1

        # Target backend runtime.
        t0 = time.perf_counter()
        target_report = run_compile(
            xc,
            backend=args.backend,
            model_path=args.model or None,
            hierarchical=args.hierarchical,
            model_attempts=args.attempts,
            model_seed=args.seed,
            no_cuda=args.no_cuda,
            run_qemu=True,
        )
        elapsed = time.perf_counter() - t0
        total_target_sec += elapsed

        target_qemu_exit = _qemu_exit(target_report)
        target_ok = target_qemu_exit is not None
        if target_ok:
            target_runtime_ok += 1
        if _assemble_ok(target_report):
            target_asm_ok += 1

        matched = bool(oracle_ok and target_ok and oracle_qemu_exit == target_qemu_exit)
        if matched:
            runtime_match += 1

        details.append(
            {
                "id": rid,
                "feature_tags": row.get("feature_tags", []),
                "oracle_qemu_exit": oracle_qemu_exit,
                "target_qemu_exit": target_qemu_exit,
                "runtime_match_oracle": matched,
                "target_compile_exit_code": target_report.get("exit_code"),
                "target_strategy_used": target_report.get("strategy_used"),
                "target_assemble_ok": _assemble_ok(target_report),
                "target_elapsed_sec": round(elapsed, 6),
            }
        )
        print(
            f"[{i}/{n}] {rid} "
            f"oracle={oracle_qemu_exit} target={target_qemu_exit} match={matched} "
            f"t={elapsed:.2f}s"
        )

    denom = max(1, n - skipped)
    summary = {
        "dataset": str(dataset),
        "rows_total": n,
        "rows_skipped": skipped,
        "backend": args.backend,
        "model": args.model,
        "oracle_runtime_ok": oracle_runtime_ok,
        "target_runtime_ok": target_runtime_ok,
        "target_assemble_ok": target_asm_ok,
        "runtime_match_oracle": runtime_match,
        "runtime_match_rate": runtime_match / denom,
        "target_runtime_ok_rate": target_runtime_ok / denom,
        "target_assemble_ok_rate": target_asm_ok / denom,
        "mean_target_elapsed_sec": total_target_sec / denom,
        "toolchain": {
            "gcc": info.get("gcc"),
            "qemu": info.get("qemu"),
        },
    }

    out = Path(args.out) if args.out else ROOT / "reports" / f"linux_exec_validate_{args.backend}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nReport written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

