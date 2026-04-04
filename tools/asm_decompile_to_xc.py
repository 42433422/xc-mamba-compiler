#!/usr/bin/env python3
"""
将 RISC-V64 GNU 汇编（与 xc_asm_oracle 生成风格一致）反编译为 XC。

示例:
  python tools/asm_decompile_to_xc.py path/to/oracle.s
  python tools/asm_decompile_to_xc.py --jsonl dataset/xc_asm_test.jsonl --field asm_riscv64 --limit 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.asm_to_xc import AsmDecompileUnsupported, decompile_oracle_asm_to_xc  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="汇编 → XC（Oracle 风格）")
    ap.add_argument("path", nargs="?", help="含 main 的 .s 文件路径")
    ap.add_argument("--jsonl", type=Path, help="从 JSONL 读取 asm 字段")
    ap.add_argument("--field", default="asm_riscv64", help="JSONL 中的汇编字段名")
    ap.add_argument("--limit", type=int, default=0, help="JSONL 最多处理行数，0 表示全部")
    ap.add_argument("--id", dest="row_id", help="仅处理指定 id 行")
    args = ap.parse_args()

    if args.jsonl:
        n = 0
        for line in args.jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if args.row_id and row.get("id") != args.row_id:
                continue
            asm = row.get(args.field) or ""
            if not asm:
                continue
            try:
                xc = decompile_oracle_asm_to_xc(asm)
            except AsmDecompileUnsupported as e:
                print(f"# skip {row.get('id')}: {e}", file=sys.stderr)
                continue
            print(f"### {row.get('id', '?')}\n{xc}")
            n += 1
            if args.limit and n >= args.limit:
                break
        return

    if not args.path:
        ap.error("请指定 .s 路径或使用 --jsonl")
    asm = Path(args.path).read_text(encoding="utf-8")
    try:
        print(decompile_oracle_asm_to_xc(asm), end="")
    except AsmDecompileUnsupported as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
