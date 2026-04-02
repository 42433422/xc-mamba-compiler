#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JNCC 语料规模预设：固定 train/val/test 比例由 build_xc_asm_corpus 保证。
用法:
  python dataset/jncc_corpus_presets.py apply smoke
  python dataset/jncc_corpus_presets.py apply medium
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRESETS = {
    "smoke": {"count": 200, "seed": 42, "prefix": "xc_asm"},
    "medium": {"count": 5000, "seed": 42, "prefix": "xc_asm"},
    "large": {"count": 50000, "seed": 42, "prefix": "xc_asm"},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "apply"])
    ap.add_argument("name", nargs="?", default="smoke")
    args = ap.parse_args()
    if args.action == "list":
        for k, v in PRESETS.items():
            print(f"{k}: count={v['count']} seed={v['seed']}")
        return
    if args.name not in PRESETS:
        print("unknown preset", args.name)
        sys.exit(1)
    p = PRESETS[args.name]
    script = ROOT / "dataset" / "build_xc_asm_corpus.py"
    cmd = [
        sys.executable,
        str(script),
        "--count",
        str(p["count"]),
        "--seed",
        str(p["seed"]),
        "--out_dir",
        str(ROOT / "dataset"),
        "--prefix",
        p["prefix"],
        "--keep_unsupported",
    ]
    print("+", " ".join(cmd))
    raise SystemExit(subprocess.call(cmd, cwd=str(ROOT)))


if __name__ == "__main__":
    main()
