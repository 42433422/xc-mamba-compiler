#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从含 pred_asm 的 JSONL 收集 assemble 失败样本，写入失败池文本（供 xc_asm_rlhf --failed_pool）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from xc_asm_validate import assemble_check


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", type=str, required=True)
    ap.add_argument("--pred_field", type=str, default="pred_asm")
    ap.add_argument("--out", type=str, default=str(ROOT / "dataset" / "jncc_failed_asm_pool.txt"))
    args = ap.parse_args()
    path = Path(args.jsonl)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as wf:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pred = row.get(args.pred_field) or ""
            if not pred.strip():
                continue
            ok, _ = assemble_check(pred)
            if not ok:
                wf.write(pred.strip() + "\n\n---\n")
                n += 1
    print(f"wrote failure blocks count~{n} to {out}")


if __name__ == "__main__":
    main()
