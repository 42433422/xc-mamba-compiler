#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第一个 AI 编译器推理：XC 源码 → RISC-V GNU 汇编（因果 LM 续写）。
训练数据格式需与 training/train_xc_mamba.py 一致。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.xc_asm_prompt import build_prompt, resolve_prompt_mode
from xc_asm_validate import assemble_check, basic_asm_sanity


def main() -> None:
    ap = argparse.ArgumentParser(description="XC → ASM (Mamba / CausalLM)")
    ap.add_argument("--model", type=str, required=True, help="本地目录或 HuggingFace id，如 models/xc-asm-mamba/final")
    ap.add_argument("--xc", type=str, default="", help="XC 源码字符串；为空则从 --file 读")
    ap.add_argument("--file", type=str, default="", help="XC 文件路径")
    ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--max_new_tokens", type=int, default=2048)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--no_cuda", action="store_true")
    ap.add_argument(
        "--prompt_mode",
        choices=["short", "teacher"],
        default="",
        help="空则使用环境变量 XC_ASM_PROMPT_MODE（默认 short）",
    )
    args = ap.parse_args()

    if args.file:
        xc = Path(args.file).read_text(encoding="utf-8")
    elif args.xc:
        xc = args.xc
    else:
        xc = sys.stdin.read()
    if not xc.strip():
        print("错误: 无 XC 输入", file=sys.stderr)
        sys.exit(1)

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("需要: pip install torch transformers", file=sys.stderr)
        sys.exit(1)

    device = "cpu" if args.no_cuda or not torch.cuda.is_available() else "cuda"
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True,
    )
    model.to(device)
    model.eval()

    pm = resolve_prompt_mode(args.prompt_mode if args.prompt_mode in ("short", "teacher") else None)
    prompt = build_prompt(xc, args.hierarchical, mode=pm)
    inputs = tok(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=args.temperature > 0,
            temperature=args.temperature if args.temperature > 0 else None,
            pad_token_id=tok.eos_token_id,
        )
    gen = tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
    asm = gen.strip()

    print("=== 生成的汇编 ===")
    print(asm)
    ok_asm, msg_asm = assemble_check(asm)
    ok_s, msg_s = basic_asm_sanity(asm)
    print("\n=== 校验 ===")
    print(f"assemble_check: {ok_asm} | {msg_asm[:200]}")
    print(f"basic_sanity:   {ok_s} | {msg_s}")


if __name__ == "__main__":
    main()
