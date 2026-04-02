#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JNCC 统一命令行：compile / bench-oracle / fuzz-xc / ir-dump
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cmd_compile(args: argparse.Namespace) -> int:
    from compiler.jncc_pipeline import run_compile, write_report

    if args.file:
        xc = Path(args.file).read_text(encoding="utf-8")
    else:
        xc = args.xc or sys.stdin.read()
    if not xc.strip():
        print("no XC input", file=sys.stderr)
        return 1

    report = run_compile(
        xc,
        backend=args.backend,
        model_path=args.model or None,
        hierarchical=args.hierarchical,
        model_attempts=args.attempts,
        model_seed=args.seed,
        no_cuda=args.no_cuda,
        run_qemu=args.qemu,
        compare_oracle=args.compare_oracle,
    )
    if args.json_log:
        write_report(Path(args.json_log), report)
    if report.get("asm") and not args.quiet_asm:
        print(report["asm"], end="" if str(report["asm"]).endswith("\n") else "\n")
    print(f"\n[jncc] exit_code={report.get('exit_code')} strategy={report.get('strategy_used')}", file=sys.stderr)
    if args.verbose:
        print(json.dumps(report, ensure_ascii=False, indent=2)[:12000])
    return int(report.get("exit_code", 1))


def cmd_bench_oracle(args: argparse.Namespace) -> int:
    from xc_asm_oracle import compile_xc_to_asm_riscv64_with_reason
    from compiler.jncc_asm_norm import normalized_asm_diff

    path = Path(args.jsonl)
    total = 0
    oracle_ok = 0
    compared = 0
    equal = 0
    assemble_ok = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            xc = row.get("xc_source") or ""
            gold = row.get("asm_riscv64") or ""
            total += 1
            ores = compile_xc_to_asm_riscv64_with_reason(xc)
            if not ores.get("ok"):
                continue
            oracle_ok += 1
            gold = gold or (ores.get("asm") or "")
            pred = row.get(args.pred_field) or ""
            if args.model:
                from compiler.jncc_model_infer import generate_asm_attempts

                asm, _ = generate_asm_attempts(
                    xc,
                    args.model,
                    hierarchical=args.hierarchical,
                    attempts=args.attempts,
                    seed=args.seed,
                    no_cuda=args.no_cuda,
                )
                pred = asm or ""
            from xc_asm_validate import assemble_check

            ok_as, _ = assemble_check(pred)
            if ok_as:
                assemble_ok += 1
            if pred.strip():
                compared += 1
                if normalized_asm_diff(pred, gold).get("equal_normalized"):
                    equal += 1

    print(
        json.dumps(
            {
                "rows_total": total,
                "oracle_ok_subset": oracle_ok,
                "pred_nonempty_compared": compared,
                "normalized_equal_vs_gold": equal,
                "assemble_pass_on_pred": assemble_ok,
                "oracle_match_rate": (equal / compared) if compared else 0.0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_fuzz_xc(args: argparse.Namespace) -> int:
    from dataset.xc_asm_synth import generate_one_with_meta
    from xc_asm_validate import mutate_xc_source_light

    rng = random.Random(args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out_path, "w", encoding="utf-8") as wf:
        while n < args.count:
            meta = generate_one_with_meta(rng)
            xc0 = meta["xc_source"]
            xc1 = mutate_xc_source_light(xc0, rng)
            rec = {"xc_source": xc0, "xc_mutated": xc1, "feature_tags": meta.get("feature_tags"), "difficulty_level": meta.get("difficulty_level")}
            wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} lines to {out_path}")
    return 0


def cmd_ir_dump(args: argparse.Namespace) -> int:
    from xc_asm_oracle import parse_xc_program
    from compiler.jncc_ir_v0 import ast_to_ir_v0, fold_constants_ir, ir_schema_v0, ir_to_xc_program, prune_unreachable_ir

    if args.file:
        xc = Path(args.file).read_text(encoding="utf-8")
    elif args.xc:
        xc = args.xc
    else:
        xc = sys.stdin.read()
    prog = parse_xc_program(xc)
    ir = ast_to_ir_v0(prog)
    if args.optimize:
        ir = fold_constants_ir(ir)
        ir = prune_unreachable_ir(ir)
    if args.schema:
        print(json.dumps(ir_schema_v0(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(ir, ensure_ascii=False, indent=2))
    if args.emit_xc:
        print("--- xc ---")
        print(ir_to_xc_program(ir))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="jncc", description="JNCC compiler CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("compile", help="XC -> asm (oracle | model | hybrid | ir)")
    p1.add_argument("--xc", default="", help="inline XC")
    p1.add_argument("--file", "-f", default="", help="XC file")
    p1.add_argument("--backend", choices=["oracle", "model", "hybrid", "ir"], default="oracle")
    p1.add_argument("--model", default="", help="checkpoint dir (e.g. models/JNCC/final)")
    p1.add_argument("--hierarchical", action="store_true")
    p1.add_argument("--attempts", type=int, default=4)
    p1.add_argument("--seed", type=int, default=None)
    p1.add_argument("--no_cuda", action="store_true")
    p1.add_argument("--qemu", action="store_true", help="try qemu after assemble (needs riscv gcc+qemu)")
    p1.add_argument("--compare-oracle", action="store_true")
    p1.add_argument("--json-log", default="", help="write full JSON report")
    p1.add_argument("--verbose", "-v", action="store_true")
    p1.add_argument("--quiet-asm", action="store_true", help="only JSON log / stderr")
    p1.set_defaults(_fn=cmd_compile)

    p2 = sub.add_parser("bench-oracle", help="JSONL benchmark: pred vs oracle asm")
    p2.add_argument("--jsonl", required=True)
    p2.add_argument("--pred_field", default="pred_asm")
    p2.add_argument("--model", default="", help="if set, run model for each row")
    p2.add_argument("--hierarchical", action="store_true")
    p2.add_argument("--attempts", type=int, default=2)
    p2.add_argument("--seed", type=int, default=None)
    p2.add_argument("--no_cuda", action="store_true")
    p2.set_defaults(_fn=cmd_bench_oracle)

    p3 = sub.add_parser("fuzz-xc", help="emit fuzz/mutated XC lines for DPO pools")
    p3.add_argument("--count", type=int, default=50)
    p3.add_argument("--seed", type=int, default=42)
    p3.add_argument("--out", type=str, default=str(ROOT / "dataset" / "jncc_fuzz_xc.jsonl"))
    p3.set_defaults(_fn=cmd_fuzz_xc)

    p4 = sub.add_parser("ir-dump", help="print IR v0 JSON for XC")
    p4.add_argument("--file", "-f", default="")
    p4.add_argument("--xc", default="")
    p4.add_argument("--optimize", action="store_true")
    p4.add_argument("--emit-xc", action="store_true")
    p4.add_argument("--schema", action="store_true", help="print IR schema only")
    p4.set_defaults(_fn=cmd_ir_dump)

    args = ap.parse_args()
    return int(args._fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
