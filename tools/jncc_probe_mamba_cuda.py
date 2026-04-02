#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 Mamba CUDA 快路径是否可用（HF kernels / mamba-ssm / nvcc）。"""
from __future__ import annotations

import shutil
import subprocess
import sys


def main() -> int:
    print("=== nvcc (CUDA Toolkit) ===")
    nvcc = shutil.which("nvcc")
    if nvcc:
        try:
            r = subprocess.run([nvcc, "--version"], capture_output=True, text=True, timeout=10)
            print(r.stdout or r.stderr or "(no output)")
        except Exception as e:  # noqa: BLE001
            print("run failed:", e)
    else:
        print("未找到 nvcc。若要从源码编 mamba-ssm/causal-conv1d，请安装 CUDA Toolkit 并把 bin 加入 PATH。")

    print("\n=== pip: mamba_ssm / causal_conv1d ===")
    for mod in ("mamba_ssm", "causal_conv1d"):
        try:
            __import__(mod)
            print(f"  import {mod}: OK")
        except ImportError as e:
            print(f"  import {mod}: NO ({e})")

    print("\n=== Hugging Face kernels hub: mamba-ssm ===")
    try:
        from kernels import get_kernel

        k = get_kernel("kernels-community/mamba-ssm", version=1)
        fn = getattr(k, "selective_scan_fn", None)
        print("  get_kernel: OK", "selective_scan_fn=" + ("set" if fn else "missing"))
    except Exception as e:  # noqa: BLE001
        print("  get_kernel: FAILED —", type(e).__name__, e)
        print("  说明: Windows 上 Hub 常无匹配你 torch/CUDA 的预编译包，会回落到慢路径。")

    print("\n=== 建议 ===")
    print("  1) 最省事且成功率高: WSL2 Ubuntu + 与 PyTorch 一致的 CUDA，再执行:")
    print("       pip install mamba-ssm[causal-conv1d] --no-build-isolation")
    print("  2) 坚持原生 Windows: 安装 CUDA Toolkit(含 nvcc) + VS2022「使用 C++ 的桌面开发」，再试上述 pip（仍可能需改源码/看 state-spaces/mamba Issue）。")
    print("  3) 无快路径时训练仍可进行，只是更慢。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
