#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 JNCC 训练/推理所需包是否可 import 并打印版本。"""
from __future__ import annotations

import importlib
import sys


def main() -> int:
    ok = True
    for name in ("torch", "transformers", "datasets", "accelerate"):
        try:
            m = importlib.import_module(name)
            ver = getattr(m, "__version__", "?")
            print(f"OK  {name:16s} {ver}")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {name:16s} {e}", file=sys.stderr)
            ok = False
    if ok:
        try:
            import torch

            print(f"cuda_available={torch.cuda.is_available()}")
            if torch.cuda.is_available():
                print(f"device={torch.cuda.get_device_name(0)}")
        except Exception:
            pass
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
