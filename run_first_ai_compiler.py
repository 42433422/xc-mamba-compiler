#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第一个 AI 编译器：一键准备数据 → Mamba 微调 →（可选）验证门控。

用法:
  python run_first_ai_compiler.py prepare --count 500
  python run_first_ai_compiler.py train
  # train 默认: batch_size=1, max_len=512, phase=base, 无 fp16（8GB 稳妥）；全量用 --phase mix --max_len 0
  python run_first_ai_compiler.py gate
  python run_first_ai_compiler.py demo   # 仅 Oracle 对照，不加载神经网络
  python jncc_cli.py compile --backend oracle -f your.xc --json-log report.json
  python dataset/jncc_corpus_presets.py apply medium
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_TRAIN = ROOT / "dataset" / "xc_asm_train.jsonl"
DATA_VAL = ROOT / "dataset" / "xc_asm_val.jsonl"
MODEL_OUT = ROOT / "models" / "JNCC" / "final"


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def cmd_prepare(args: argparse.Namespace) -> int:
    script = ROOT / "dataset" / "build_xc_asm_corpus.py"
    if not script.is_file():
        print("缺少", script)
        return 1
    return run(
        [
            sys.executable,
            str(script),
            "--count",
            str(args.count),
            "--seed",
            str(args.seed),
            "--out_dir",
            str(ROOT / "dataset"),
            "--prefix",
            "xc_asm",
            "--keep_unsupported",
        ]
    )


def cmd_train(args: argparse.Namespace) -> int:
    script = ROOT / "training" / "train_xc_mamba.py"
    if not DATA_TRAIN.is_file():
        print(f"缺少训练数据 {DATA_TRAIN}，先运行: python run_first_ai_compiler.py prepare")
        return 1
    return run(
        [
            sys.executable,
            str(script),
            "--jsonl",
            str(DATA_TRAIN),
            "--model",
            args.model,
            "--output_dir",
            str(ROOT / "models" / args.out_name),
            "--epochs",
            str(args.epochs),
            "--batch_size",
            str(args.batch_size),
            "--lr",
            str(args.lr),
            "--curriculum_phase",
            args.phase,
        ]
        + ["--max_len", str(args.max_len)]
        + (["--fp16"] if args.fp16 else [])
        + (["--feature_balanced_sampling"] if args.balanced else [])
        + (["--hierarchical"] if args.hierarchical else [])
    )


def cmd_gate(_: argparse.Namespace) -> int:
    script = ROOT / "training" / "eval_gate_assemble.py"
    if not DATA_VAL.is_file():
        print(f"缺少 {DATA_VAL}")
        return 1
    return run(
        [
            sys.executable,
            str(script),
            "--jsonl",
            str(DATA_VAL),
            "--threshold",
            "0.99",
        ]
    )


def cmd_demo(_: argparse.Namespace) -> int:
    from xc_asm_oracle import compile_xc_to_asm_riscv64_with_reason

    sample = """# {
    $x: int = 3
    $y: int = 4
    ^ x + y
}"""
    r = compile_xc_to_asm_riscv64_with_reason(sample)
    print("Oracle（规则真值）汇编:")
    print(r.get("asm") or "(无)")
    print("unsupported_reason:", r.get("unsupported_reason"))
    print("\n训练完成后，用同一 XC 测试 AI:")
    print(f'  python inference/xc_compile_ml.py --model "{MODEL_OUT}" --xc \'{sample}\'')
    print("或统一入口:")
    print(f'  python jncc_cli.py compile --backend hybrid --model "{MODEL_OUT}" --xc \'{sample}\'')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="第一个 AI 编译器流水线")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p0 = sub.add_parser("prepare", help="生成/刷新 XC↔ASM 数据集")
    p0.add_argument("--count", type=int, default=800)
    p0.add_argument("--seed", type=int, default=42)

    p1 = sub.add_parser("train", help="Mamba 监督微调")
    p1.add_argument("--model", choices=["mamba-130m", "mamba-370m"], default="mamba-130m")
    p1.add_argument("--out_name", type=str, default="JNCC")
    p1.add_argument("--epochs", type=int, default=2)
    p1.add_argument("--batch_size", type=int, default=1)
    p1.add_argument("--lr", type=float, default=2e-4)
    p1.add_argument(
        "--max_len",
        type=int,
        default=512,
        help="0 表示交给 train_xc_mamba 使用模型默认长度(4096)",
    )
    p1.add_argument("--fp16", action="store_true", help="开启半精度（需与 torch/transformers 版本匹配）")
    p1.add_argument("--phase", choices=["base", "feature", "mix"], default="base")
    p1.add_argument("--balanced", action="store_true")
    p1.add_argument("--hierarchical", action="store_true")

    sub.add_parser("gate", help="验证集 assemble 门控")

    sub.add_parser("demo", help="打印 Oracle 示例与推理命令")

    args = ap.parse_args()
    if args.cmd == "prepare":
        return cmd_prepare(args)
    if args.cmd == "train":
        return cmd_train(args)
    if args.cmd == "gate":
        return cmd_gate(args)
    if args.cmd == "demo":
        return cmd_demo(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
