"""JNCC 模型推理：多轮采样 + 与训练脚本一致的 prompt。"""

from __future__ import annotations

import random
from typing import Any, List, Tuple

from xc_asm_validate import assemble_check, basic_asm_sanity


def build_prompt(xc_source: str, hierarchical: bool) -> str:
    instr = "将 XC 翻译为 RISC-V64 GNU 汇编，只输出汇编，不要解释。"
    inp = xc_source.strip()
    if hierarchical:
        lines = [ln for ln in inp.splitlines() if ln.strip()]
        hier = ["<<<PROGRAM>>>"] + [f"<<<STMT_{i}>>>{ln}" for i, ln in enumerate(lines)]
        inp = "\n".join(hier)
    return f"{instr}\n\n### 输入\n{inp}\n\n### 汇编\n"


def generate_asm_attempts(
    xc: str,
    model_path: str,
    *,
    hierarchical: bool = False,
    max_new_tokens: int = 2048,
    attempts: int = 4,
    temperatures: Tuple[float, ...] = (0.0, 0.2, 0.4, 0.6),
    seed: int | None = None,
    no_cuda: bool = False,
) -> Tuple[str | None, List[dict[str, Any]]]:
    """
    返回 (第一条通过 assemble_check 的 asm, 每轮详情列表)。
    temperatures 长度不足时用最后一项填充。
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)

    device = "cpu" if no_cuda or not torch.cuda.is_available() else "cuda"
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True,
    )
    model.to(device)
    model.eval()

    prompt = build_prompt(xc, hierarchical)
    inputs = tok(prompt, return_tensors="pt").to(device)
    details: List[dict[str, Any]] = []
    temps = list(temperatures)
    while len(temps) < attempts:
        temps.append(temps[-1])

    for i in range(attempts):
        t = temps[i]
        do_sample = t > 0
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=t if do_sample else None,
                pad_token_id=tok.eos_token_id,
            )
        gen = tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        asm = gen.strip()
        ok_a, msg_a = assemble_check(asm)
        ok_s, msg_s = basic_asm_sanity(asm)
        rec = {
            "attempt": i + 1,
            "temperature": t,
            "assemble_ok": ok_a,
            "assemble_msg": msg_a[:500],
            "sanity_ok": ok_s,
            "sanity_msg": msg_s,
            "asm_preview": asm[:400],
        }
        details.append(rec)
        if ok_a and ok_s:
            return asm, details
    return None, details


def load_causal_lm_bundle(
    model_path: str,
    *,
    no_cuda: bool = False,
):
    """加载 tokenizer + model，供批量评测复用（单次贪心解码见 generate_asm_greedy_timed）。"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cpu" if no_cuda or not torch.cuda.is_available() else "cuda"
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True,
    )
    model.to(device)
    model.eval()
    return {"tok": tok, "model": model, "device": device}


def generate_asm_greedy_timed(
    bundle: dict,
    xc: str,
    *,
    hierarchical: bool = False,
    max_new_tokens: int = 2048,
) -> tuple[str, float]:
    """单次贪心生成汇编，返回 (文本, 秒)。不调用 assemble_check。"""
    import time

    import torch

    tok = bundle["tok"]
    model = bundle["model"]
    device = bundle["device"]
    prompt = build_prompt(xc, hierarchical)
    inputs = tok(prompt, return_tensors="pt").to(device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tok.eos_token_id,
        )
    dt = time.perf_counter() - t0
    gen = tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
    return gen.strip(), dt
