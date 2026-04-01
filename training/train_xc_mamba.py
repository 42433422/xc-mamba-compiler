#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XC→ASM 使用 Mamba 架构训练入口（单卡友好）。
- 复用现有 JSONL 数据与课程学习筛选
- 默认模型: state-spaces/mamba-130m-hf
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


def row_to_text(row: dict, hierarchical: bool, template_id: int) -> str:
    instr = [
        "将 XC 翻译为 RISC-V64 GNU 汇编，只输出汇编，不要解释。",
        "Translate XC to RISC-V64 GNU assembly only.",
        "[Hierarchical] use <<<PROGRAM>>> / <<<STMT_n>>> to understand structure.",
    ][template_id % 3]
    inp = row["hierarchical_input"] if hierarchical else row["xc_source"]
    out = (row.get("asm_riscv64") or "").strip()
    return f"{instr}\n\n### 输入\n{inp}\n\n### 汇编\n{out}"


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
    ap.add_argument("--output_dir", type=str, default=str(ROOT / "models" / "xc-asm-mamba"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch_size", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max_len", type=int, default=0, help="override model max sequence length")
    ap.add_argument("--curriculum_phase", choices=["base", "feature", "mix"], default="mix")
    ap.add_argument("--feature_balanced_sampling", action="store_true")
    ap.add_argument("--fp16", action="store_true", help="enable fp16 training")
    ap.add_argument("--dry_run", action="store_true")
    args = ap.parse_args()

    jsonl_path = Path(args.jsonl)
    if not jsonl_path.is_file():
        print(f"missing dataset: {jsonl_path}")
        sys.exit(1)

    rows = load_jsonl(jsonl_path)
    rows = phase_filter(rows, args.curriculum_phase)
    if args.feature_balanced_sampling:
        rows = balanced_by_feature(rows)
    texts = [row_to_text(r, args.hierarchical, i) for i, r in enumerate(rows)]
    print(
        f"[data] {len(texts)} rows, hierarchical={args.hierarchical}, "
        f"phase={args.curriculum_phase}, balanced={args.feature_balanced_sampling}"
    )
    if args.dry_run:
        print(texts[0][:1800] if texts else "<empty>")
        return

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

    tokenizer = AutoTokenizer.from_pretrained(cfg["name"], trust_remote_code=True)
    load_dtype = torch.float16 if args.fp16 else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        cfg["name"],
        torch_dtype=load_dtype,
        device_map="auto",
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    ds = Dataset.from_dict({"text": texts})
    effective_max_len = args.max_len if args.max_len and args.max_len > 0 else cfg["max_len"]
    tds = tokenize_dataset(ds, tokenizer, effective_max_len)
    collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

    training_args = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        logging_steps=10,
        save_steps=200,
        fp16=bool(args.fp16),
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tds,
        data_collator=collator,
    )
    trainer.train()
    model.save_pretrained(str(out_dir / "final"))
    tokenizer.save_pretrained(str(out_dir / "final"))
    print(f"[done] model saved: {out_dir / 'final'}")


if __name__ == "__main__":
    main()
