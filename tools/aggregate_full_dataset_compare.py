#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并全量评测 JSON，生成一份「金标 / Oracle 自测 /（可选）模型」对比摘要。

读取（若存在）:
  - reports/linux_exec_validate_gold_full.json
  - reports/linux_exec_validate_oracle_self_xc_asm_all.json
  - reports/linux_exec_validate_model_xc_asm_all.json  （由 Docker 对 pred_model_xc_asm_all.jsonl 生成）

输出:
  - reports/full_dataset_compare_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]


def _read_summary(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("summary") if isinstance(data, dict) else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate full-dataset validation reports.")
    ap.add_argument("--out", type=str, default=str(ROOT / "reports" / "full_dataset_compare_summary.json"))
    args = ap.parse_args()

    gold = _read_summary(ROOT / "reports" / "linux_exec_validate_gold_full.json")
    oracle_self = _read_summary(ROOT / "reports" / "linux_exec_validate_oracle_self_xc_asm_all.json")
    model_rep = _read_summary(ROOT / "reports" / "linux_exec_validate_model_xc_asm_all.json")

    rows = None
    if gold and isinstance(gold.get("rows"), int):
        rows = gold["rows"]

    compare: Dict[str, Any] = {
        "dataset": str((ROOT / "dataset" / "xc_asm_all.jsonl").resolve()),
        "rows": rows,
        "metrics_reference": str((ROOT / "dataset" / "evaluation_spec.json").resolve()),
        "A_gold_qemu_ok_rate": gold.get("gold_qemu_ok_rate") if gold else None,
        "A_oracle_self_runtime_match_rate": oracle_self.get("runtime_match_rate") if oracle_self else None,
        "B_oracle_self_normalized_asm_match_rate": oracle_self.get("normalized_asm_match_rate") if oracle_self else None,
        "A_model_runtime_match_rate": model_rep.get("runtime_match_rate") if model_rep else None,
        "B_model_normalized_asm_match_rate": model_rep.get("normalized_asm_match_rate") if model_rep else None,
        "model_pred_report_missing": model_rep is None,
        "source_reports": {
            "gold": str(ROOT / "reports" / "linux_exec_validate_gold_full.json"),
            "oracle_self": str(ROOT / "reports" / "linux_exec_validate_oracle_self_xc_asm_all.json"),
            "model": str(ROOT / "reports" / "linux_exec_validate_model_xc_asm_all.json"),
        },
        "raw_summaries": {
            "gold": gold,
            "oracle_self_pred_equals_oracle": oracle_self,
            "model_vs_oracle": model_rep,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(compare, ensure_ascii=False, indent=2))
    print(f"\nWrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
