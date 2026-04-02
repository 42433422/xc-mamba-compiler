#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态指令条数对比：两个 .s 文本或 JSONL 中 asm 字段。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def count_instr(asm: str) -> int:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=str, help="file path asm A")
    ap.add_argument("--b", type=str, help="file path asm B")
    ap.add_argument("--jsonl", type=str, help="JSONL with asm_riscv64 + pred_asm")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    if args.a and args.b:
        ta = Path(args.a).read_text(encoding="utf-8")
        tb = Path(args.b).read_text(encoding="utf-8")
        ca, cb = count_instr(ta), count_instr(tb)
        print(json.dumps({"count_a": ca, "count_b": cb, "ratio_b_over_a": (cb / ca) if ca else None}, indent=2))
        return
    if args.jsonl:
        path = Path(args.jsonl)
        rows = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= args.limit:
                    break
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                g = r.get("asm_riscv64") or ""
                p = r.get("pred_asm") or g
                rows.append(
                    {
                        "id": r.get("id"),
                        "gold_lines": count_instr(g),
                        "pred_lines": count_instr(p),
                    }
                )
        print(json.dumps({"samples": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
        return
    print("need --a/--b or --jsonl", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
