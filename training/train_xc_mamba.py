#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XC→ASM 使用 Mamba 架构训练入口（单卡友好）。
- 复用现有 JSONL 数据与课程学习筛选
- 默认模型: state-spaces/mamba-130m-hf
- 默认 batch_size=1、max_len=512、fp16 关闭，适配常见 8GB 显存；大显存可用 --max_len 0 与 --fp16。
- 若已安装 `kernels` 包，新版 Transformers 会在构建 Mamba 时从 Hub 拉取 causal-conv1d/mamba-ssm；
  网络或代理不稳会报错；可加 --no_hub_kernels 走 PyTorch 慢速实现（仍可训练，单步更慢）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.xc_asm_prompt import build_training_input_body, format_xc_asm_prompt


MODEL_CONFIGS = {
    "mamba-130m": {"name": "state-spaces/mamba-130m-hf", "max_len": 4096},
    "mamba-370m": {"name": "state-spaces/mamba-370m-hf", "max_len": 4096},
}


def load_jsonl(path: Path) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def phase_filter(rows: List[dict], phase: str) -> List[dict]:
    if phase == "base":
        return [r for r in rows if r.get("difficulty_level") == "easy"]
    if phase == "feature":
        return [r for r in rows if r.get("difficulty_level") in ("medium", "hard")]
    return rows


def balanced_by_feature(rows: List[dict], cap_per_tag: int = 20000) -> List[dict]:
    buckets: Dict[str, List[dict]] = {}
    for r in rows:
        tags = r.get("feature_tags") or ["_untagged"]
        buckets.setdefault(tags[0], []).append(r)
    out: List[dict] = []
    for _, items in buckets.items():
        out.extend(items[:cap_per_tag])
    return out


def row_to_text(row: dict, hierarchical: bool, template_id: int, prompt_mode: str) -> str:
    inp = build_training_input_body(row, hierarchical)
    out = (row.get("asm_riscv64") or "").strip()
    return format_xc_asm_prompt(inp, "teacher" if prompt_mode == "teacher" else "short", template_id) + out


def tokenize_dataset(ds: Any, tokenizer, max_len: int) -> Any:
    def tok(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_len,
            padding="max_length",
        )

    return ds.map(tok, batched=True, remove_columns=["text"])


def main() -> None:
    ap = argparse.ArgumentParser(description="XC→ASM with Mamba")
    ap.add_argument("--jsonl", type=str, default=str(ROOT / "dataset" / "xc_asm_train.jsonl"))
    ap.add_argument("--hierarchical", action="store_true")
    ap.add_argument("--model", choices=["mamba-130m", "mamba-370m"], default="mamba-130m")
    ap.add_argument(
        "--base_model",
        type=str,
        default="",
        help="覆盖默认 Hub 名：填本地目录（如 models/JNCC/final）则从该路径加载权重与 tokenizer",
    )
    ap.add_argument("--output_dir", type=str, default=str(ROOT / "models" / "JNCC"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch_size", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument(
        "--max_len",
        type=int,
        default=512,
        help="序列长度上限；0 表示使用模型配置中的 max_len（如 4096），8GB 卡建议保持默认 512",
    )
    ap.add_argument(
        "--curriculum_phase",
        choices=["base", "feature", "mix"],
        default="base",
        help="base=仅 easy 子集，适合先跑通；mix=全难度",
    )
    ap.add_argument("--feature_balanced_sampling", action="store_true")
    ap.add_argument(
        "--prompt_mode",
        choices=["short", "teacher"],
        default="short",
        help="训练提示词；teacher 与推理环境变量 XC_ASM_PROMPT_MODE=teacher 对齐",
    )
    ap.add_argument("--fp16", action="store_true", help="AMP fp16（权重保持 FP32，避免 unscale 报错）")
    ap.add_argument(
        "--max_steps",
        type=int,
        default=0,
        help=">0 时优先于 epochs，用于冒烟/调试（例如 20）",
    )
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument(
        "--no_hub_kernels",
        action="store_true",
        help="阻止从 Hugging Face Hub 下载 Mamba 内核包（避免 kernels 触发 snapshot_download 失败；用慢速回退）",
    )
    args = ap.parse_args()

    jsonl_path = Path(args.jsonl)
    if not jsonl_path.is_file():
        print(f"missing dataset: {jsonl_path}")
        sys.exit(1)

    rows = load_jsonl(jsonl_path)
    rows = phase_filter(rows, args.curriculum_phase)
    if args.feature_balanced_sampling:
        rows = balanced_by_feature(rows)
    texts = [row_to_text(r, args.hierarchical, i, args.prompt_mode) for i, r in enumerate(rows)]
    print(
        f"[data] {len(texts)} rows, hierarchical={args.hierarchical}, "
        f"phase={args.curriculum_phase}, balanced={args.feature_balanced_sampling}, "
        f"prompt_mode={args.prompt_mode}"
    )
    if args.dry_run:
        print(texts[0][:1800] if texts else "<empty>")
        return

    if args.no_hub_kernels:
        import types

        # 在加载 transformers 之前占位，使 integrations.hub_kernels 的 `from kernels import ...` 失败，
        # 从而 lazy_load_kernel 走本地 causal_conv1d / 纯 PyTorch 回退，不再访问 Hub。
        sys.modules["kernels"] = types.ModuleType("kernels")

    try:
        import torch
        from datasets import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as e:
        print(f"need: pip install torch transformers datasets accelerate\n{e}")
        sys.exit(1)

    cfg = MODEL_CONFIGS[args.model]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_id = (args.base_model or "").strip() or cfg["name"]
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    # FP16 训练须加载 FP32 权重，由 Trainer fp16=True 做 autocast；直接 float16 权重会触发 grad scaler 错误。
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float32,
        device_map="auto",
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    ds = Dataset.from_dict({"text": texts})
    effective_max_len = args.max_len if args.max_len and args.max_len > 0 else cfg["max_len"]
    tds = tokenize_dataset(ds, tokenizer, effective_max_len)
    collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

    ta_kw = dict(
        output_dir=str(out_dir / "checkpoints"),
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        logging_steps=10,
        save_steps=max(200, args.max_steps * 2) if args.max_steps > 0 else 200,
        fp16=bool(args.fp16),
    )
    if args.max_steps > 0:
        training_args = TrainingArguments(max_steps=args.max_steps, **ta_kw)
    else:
        training_args = TrainingArguments(num_train_epochs=args.epochs, **ta_kw)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tds,
        data_collator=collator,
    )
    trainer.train()
    model.save_pretrained(str(out_dir / "final"))
    tokenizer.save_pretrained(str(out_dir / "final"))
    try:
        import importlib.metadata as im

        repro = {
            "torch": getattr(torch, "__version__", ""),
            "transformers": im.version("transformers"),
            "datasets": im.version("datasets"),
            "accelerate": im.version("accelerate"),
            "base_model": model_id,
            "config_preset": args.model,
        }
        (out_dir / "final" / "jncc_repro.json").write_text(
            json.dumps(repro, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
    print(f"[done] model saved: {out_dir / 'final'}")


if __name__ == "__main__":
    main()
