#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写入当前环境关键包版本到 models/jncc_repro_env.json（不覆盖已有 checkpoint 内 jncc_repro.json）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    try:
        import importlib.metadata as im
    except ImportError:
        print("needs Python 3.8+", file=sys.stderr)
        sys.exit(1)
    pkgs = ["torch", "transformers", "datasets", "accelerate", "peft", "numpy"]
    out = {}
    for p in pkgs:
        try:
            out[p] = im.version(p)
        except Exception:
            out[p] = "missing"
    p = ROOT / "models" / "jncc_repro_env.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
