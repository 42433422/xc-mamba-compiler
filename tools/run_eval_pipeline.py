#!/usr/bin/env python3
"""
端到端评测：生成 pred_asm → QEMU 对拍（可选规范化汇编接近度）。
依赖本机 torch + 模型目录；无工具链时第二步需在 Docker 内单独运行。

示例:
  python tools/run_eval_pipeline.py --model models/JNCC/final \\
    --jsonl dataset/xc_asm_test.jsonl --limit 10 --prompt_mode teacher --proximity

Docker 内仅跑第二步:
  python tools/jncc_linux_exec_validate_from_pred_asm.py --jsonl reports/pred_eval.jsonl --proximity
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate pred_asm then validate (two-step).")
    ap.add_argument("--model", type=str, default="", help="oracle_self_test 时不需要")
    ap.add_argument("--jsonl", type=str, default=str(ROOT / "dataset" / "xc_asm_test.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="0 = all rows in jsonl")
    ap.add_argument("--prompt_mode", type=str, default="teacher", choices=["", "short", "teacher"])
    ap.add_argument("--no_cuda", action="store_true")
    ap.add_argument("--pred_out", type=str, default=str(ROOT / "reports" / "pred_eval.jsonl"))
    ap.add_argument("--report_out", type=str, default=str(ROOT / "reports" / "linux_exec_validate_from_pred_eval.json"))
    ap.add_argument("--proximity", action="store_true")
    ap.add_argument("--skip_generate", action="store_true", help="仅运行验证（pred_out 已存在）")
    ap.add_argument(
        "--oracle_self_test",
        action="store_true",
        help="不写模型：将 asm_riscv64 复制为 pred_asm，用于打通评测链路与 CI（全量测试集秒级完成）",
    )
    args = ap.parse_args()

    pred_path = Path(args.pred_out)
    pred_path.parent.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    if args.oracle_self_test and not args.skip_generate:
        src = Path(args.jsonl)
        lim = args.limit
        rows_out = []
        with open(src, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                row = dict(row)
                row["pred_asm"] = row.get("asm_riscv64") or ""
                row["t_gen_sec"] = 0.0
                row["pred_generated"] = True
                row["pred_asm_validated"] = True
                rows_out.append(json.dumps(row, ensure_ascii=False))
                if lim > 0 and len(rows_out) >= lim:
                    break
        pred_path.write_text("\n".join(rows_out) + "\n", encoding="utf-8")
        print(f"oracle_self_test: wrote {len(rows_out)} rows -> {pred_path}", flush=True)
    elif not args.skip_generate:
        if not args.model:
            print("--model required unless --oracle_self_test or --skip_generate", file=sys.stderr)
            return 2
        cmd = [
            py,
            str(ROOT / "tools" / "jncc_generate_pred_asm.py"),
            "--jsonl",
            args.jsonl,
            "--model",
            args.model,
            "--out",
            str(pred_path),
            "--attempts",
            "1",
            "--temperatures",
            "0.0",
        ]
        if args.limit > 0:
            cmd.extend(["--limit", str(args.limit)])
        if args.no_cuda:
            cmd.append("--no_cuda")
        if args.prompt_mode in ("short", "teacher"):
            cmd.extend(["--prompt_mode", args.prompt_mode])
        print("RUN", " ".join(cmd), flush=True)
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            return r.returncode

    vcmd = [
        py,
        str(ROOT / "tools" / "jncc_linux_exec_validate_from_pred_asm.py"),
        "--jsonl",
        str(pred_path),
        "--out",
        args.report_out,
        "--backend_label",
        "eval_pipeline",
    ]
    if args.proximity:
        vcmd.append("--proximity")
    print("RUN", " ".join(vcmd), flush=True)
    r2 = subprocess.run(vcmd, cwd=str(ROOT))
    return r2.returncode


if __name__ == "__main__":
    raise SystemExit(main())
