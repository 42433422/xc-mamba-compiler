#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XC → RISC-V 汇编：监督学习数据管线（JSONL → HF Dataset → 因果 LM / LoRA）。
重依赖（torch / transformers / peft / datasets）仅在非 --dry_run 时加载。
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
    "qwen2.5-coder-1.5b": {
        "name": "Qwen/Qwen2.5-Coder-1.5B",
        "max_len": 8192,
        "lora_r": 16,
        "lora_alpha": 32,
    },
}


def load_jsonl(path: Path) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _phase_filter(rows: List[dict], phase: str) -> List[dict]:
    if phase == "base":
        return [r for r in rows if r.get("difficulty_level") == "easy"]
    if phase == "feature":
        return [r for r in rows if r.get("difficulty_level") in ("medium", "hard")]
    return rows


def _balanced_by_feature(rows: List[dict], cap_per_tag: int = 20000) -> List[dict]:
    """
    轻量 feature 平衡采样：按第一标签做配额，避免高频模板主导训练。
    """
    buckets: Dict[str, List[dict]] = {}
    for r in rows:
        tags = r.get("feature_tags") or ["_untagged"]
        key = tags[0]
        buckets.setdefault(key, []).append(r)
    out: List[dict] = []
    for _, items in buckets.items():
        out.extend(items[:cap_per_tag])
    return out


def row_to_text(row: dict, hierarchical: bool, template_id: int, prompt_mode: str) -> str:
    inp = build_training_input_body(row, hierarchical)
    out = row["asm_riscv64"].strip()
    return format_xc_asm_prompt(inp, "teacher" if prompt_mode == "teacher" else "short", template_id) + out


def build_training_texts(jsonl_path: Path, hierarchical: bool, prompt_mode: str = "short") -> List[str]:
    rows = load_jsonl(jsonl_path)
    return [row_to_text(row, hierarchical, i, prompt_mode) for i, row in enumerate(rows)]


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
    ap = argparse.ArgumentParser(description="XC→ASM LoRA 监督微调")
    ap.add_argument("--jsonl", type=str, default=str(ROOT / "dataset" / "xc_asm_train.jsonl"))
    ap.add_argument("--hierarchical", action="store_true", help="使用 hierarchical_input 作为输入侧")
    ap.add_argument("--model", type=str, default="qwen2.5-coder-1.5b")
    ap.add_argument("--output_dir", type=str, default=str(ROOT / "models" / "xc-asm-translator"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch_size", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--curriculum_phase", choices=["base", "feature", "mix"], default="mix")
    ap.add_argument("--feature_balanced_sampling", action="store_true")
    ap.add_argument(
        "--prompt_mode",
        choices=["short", "teacher"],
        default="short",
        help="与 compiler/xc_asm_prompt 一致；teacher=Oracle/寄存器/RVV/流水意图说明（推荐与推理 XC_ASM_PROMPT_MODE=teacher 对齐）",
    )
    ap.add_argument("--dry_run", action="store_true", help="仅构建文本样本，不导入 torch/transformers")
    args = ap.parse_args()

    jsonl_path = Path(args.jsonl)
    if not jsonl_path.is_file():
        print(f"缺少数据: {jsonl_path} ，请先运行 dataset/build_xc_asm_jsonl.py")
        sys.exit(1)

    rows = load_jsonl(jsonl_path)
    rows = _phase_filter(rows, args.curriculum_phase)
    if args.feature_balanced_sampling:
        rows = _balanced_by_feature(rows)
    texts = [row_to_text(row, args.hierarchical, i, args.prompt_mode) for i, row in enumerate(rows)]
    print(
        f"[数据] {len(texts)} 条, hierarchical={args.hierarchical}, "
        f"phase={args.curriculum_phase}, balanced={args.feature_balanced_sampling}, "
        f"prompt_mode={args.prompt_mode}"
    )
    if args.dry_run:
        print(texts[0][:2000])
        return

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as e:
        print(f"需要: pip install torch transformers peft datasets accelerate（版本需匹配）\n{e}")
        sys.exit(1)

    try:
        from unsloth import FastLanguageModel

        HAS_UNSLOTH = True
    except ImportError:
        HAS_UNSLOTH = False

    cfg = MODEL_CONFIGS.get(args.model, MODEL_CONFIGS["qwen2.5-coder-1.5b"])
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ds = Dataset.from_dict({"text": texts})

    if HAS_UNSLOTH:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=cfg["name"],
            max_seq_length=cfg["max_len"],
            dtype=torch.float16,
            load_in_4bit=True,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=cfg["lora_r"],
            lora_alpha=cfg["lora_alpha"],
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
    else:
        tokenizer = AutoTokenizer.from_pretrained(cfg["name"], trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            cfg["name"],
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        lora = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=cfg["lora_r"],
            lora_alpha=cfg["lora_alpha"],
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
        model = get_peft_model(model, lora)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tds = tokenize_dataset(ds, tokenizer, cfg["max_len"])
    collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

    training_args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        logging_steps=10,
        save_steps=200,
        fp16=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tds,
        data_collator=collator,
    )
    trainer.train()
    model.save_pretrained(str(out_dir / "final_lora"))
    tokenizer.save_pretrained(str(out_dir / "final_lora"))
    print(f"[完成] LoRA 已保存: {out_dir / 'final_lora'}")


if __name__ == "__main__":
    main()
