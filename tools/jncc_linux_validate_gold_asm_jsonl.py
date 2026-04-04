#!/usr/bin/env python3
"""
对 JSONL 中每条样本的 asm_riscv64（Oracle 金汇编）做 gcc 静态链接 + qemu-riscv64，统计可运行率。
不调用模型。用于全量金标回归。

示例:
  python tools/jncc_linux_validate_gold_asm_jsonl.py --jsonl dataset/xc_asm_all.jsonl \\
      --out reports/linux_exec_validate_gold_full.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xc_asm_validate import get_toolchain_info, try_compile_and_qemu_exit_code  # noqa: E402


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="QEMU validate gold asm_riscv64 for each JSONL row.")
    ap.add_argument("--jsonl", type=str, required=True)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--limit", type=int, default=0, help="0 = all rows")
    args = ap.parse_args()

    info = get_toolchain_info()
    if not info.get("gcc") or not info.get("qemu"):
        print("Missing riscv64 gcc or qemu-riscv64.", info)
        return 2

    path = Path(args.jsonl)
    if not path.is_file():
        print(f"Missing: {path}")
        return 2

    rows = load_jsonl(path)
    if args.limit > 0:
        rows = rows[: args.limit]

    out_path = Path(args.out) if args.out else ROOT / "reports" / "linux_exec_validate_gold_full.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    details: List[Dict[str, Any]] = []
    ok_n = 0
    t0 = time.perf_counter()

    for i, row in enumerate(rows, start=1):
        rid = row.get("id") or f"row_{i}"
        asm = (row.get("asm_riscv64") or "").strip()
        if not asm:
            details.append({"id": rid, "ok": False, "exit_code": None, "msg": "empty_asm"})
            continue
        rc, msg = try_compile_and_qemu_exit_code(asm)
        good = rc is not None
        if good:
            ok_n += 1
        details.append(
            {
                "id": rid,
                "ok": good,
                "exit_code": rc,
                "msg": (msg or "")[:2000],
            }
        )
        print(f"[{i}/{len(rows)}] {rid} exit={rc} ok={good}")

    dt = time.perf_counter() - t0
    denom = len(rows)
    summary: Dict[str, Any] = {
        "dataset": str(path.resolve()),
        "rows": denom,
        "gold_qemu_ok": ok_n,
        "gold_qemu_ok_rate": ok_n / denom if denom else 0.0,
        "wall_sec": round(dt, 3),
        "toolchain": {"gcc": info.get("gcc"), "qemu": info.get("qemu")},
    }
    payload = {"summary": summary, "details": details}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
