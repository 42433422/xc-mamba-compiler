"""JNCC 编译流水线：Oracle / 模型 / IR 规则后端 + 结构化报告。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from compiler.jncc_errors import ERROR_DOMAIN, JNCCExitCode
from xc_asm_oracle import compile_xc_to_asm_riscv64_with_reason
from xc_asm_validate import (
    assemble_check,
    basic_asm_sanity,
    try_compile_and_qemu_exit_code,
)
from xc_preprocess import split_preprocessor_and_body
from xc_compiler import XCLexer, XCParser


def _xc_sha256(xc: str) -> str:
    norm = "\n".join(x.rstrip() for x in xc.strip().splitlines())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _parse_stage(xc: str) -> Dict[str, Any]:
    try:
        _prep, body = split_preprocessor_and_body(xc)
        lexer = XCLexer(body)
        parser = XCParser(lexer.tokenize())
        parser.parse()
        return {"ok": True, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}:{e}"}


def run_compile(
    xc: str,
    *,
    backend: str = "oracle",
    model_path: Optional[str] = None,
    hierarchical: bool = False,
    model_attempts: int = 4,
    model_seed: Optional[int] = None,
    no_cuda: bool = False,
    run_qemu: bool = False,
    compare_oracle: bool = False,
    ir_backend: bool = False,
) -> Dict[str, Any]:
    """
    backend: oracle | model | hybrid | ir
      hybrid: 先 model（多采样），失败则 Oracle。
      ir: 规则 IR v0 → asm（见 compiler.jncc_ir_v0）。
    """
    report: Dict[str, Any] = {
        "domain": ERROR_DOMAIN,
        "backend_requested": backend,
        "xc_sha256": _xc_sha256(xc),
        "model_checkpoint": model_path,
        "model_seed": model_seed,
        "stages": {},
    }

    ps = _parse_stage(xc)
    report["stages"]["parse"] = ps
    if not ps["ok"]:
        report["exit_code"] = int(JNCCExitCode.PARSE_ERROR)
        report["asm"] = None
        report["strategy_used"] = "none"
        return report

    oracle_res = compile_xc_to_asm_riscv64_with_reason(xc)
    report["stages"]["oracle"] = {
        "ok": oracle_res["ok"],
        "unsupported_reason": oracle_res.get("unsupported_reason"),
        "asm_len": len((oracle_res.get("asm") or "")),
    }

    asm_out: Optional[str] = None
    strategy = backend

    if backend == "ir":
        from compiler.jncc_ir_v0 import compile_xc_via_ir

        ir_res = compile_xc_via_ir(xc, optimize=True)
        report["stages"]["ir"] = ir_res.get("meta", {})
        if ir_res.get("ok"):
            asm_out = ir_res.get("asm")
        else:
            report["exit_code"] = int(JNCCExitCode.ORACLE_UNSUPPORTED)
            report["asm"] = None
            report["strategy_used"] = "ir_failed"
            report["error"] = ir_res.get("error")
            return report

    elif backend == "oracle":
        if oracle_res["ok"]:
            asm_out = oracle_res["asm"]
        else:
            report["exit_code"] = int(JNCCExitCode.ORACLE_UNSUPPORTED)
            report["asm"] = None
            report["strategy_used"] = "oracle"
            report["error"] = oracle_res.get("unsupported_reason")
            return report

    elif backend == "model":
        if not model_path:
            report["exit_code"] = int(JNCCExitCode.INTERNAL)
            report["error"] = "model_path required"
            report["asm"] = None
            return report
        from compiler.jncc_model_infer import generate_asm_attempts

        asm_m, details = generate_asm_attempts(
            xc,
            model_path,
            hierarchical=hierarchical,
            attempts=model_attempts,
            seed=model_seed,
            no_cuda=no_cuda,
        )
        report["stages"]["model"] = {"attempts": details}
        if asm_m:
            asm_out = asm_m
        else:
            report["exit_code"] = int(JNCCExitCode.MODEL_FAILED)
            report["asm"] = None
            report["strategy_used"] = "model"
            return report

    elif backend == "hybrid":
        asm_out = None
        if model_path:
            from compiler.jncc_model_infer import generate_asm_attempts

            asm_m, details = generate_asm_attempts(
                xc,
                model_path,
                hierarchical=hierarchical,
                attempts=model_attempts,
                seed=model_seed,
                no_cuda=no_cuda,
            )
            report["stages"]["model"] = {"attempts": details}
            if asm_m:
                asm_out = asm_m
                strategy = "hybrid_model"
        if asm_out is None and oracle_res["ok"]:
            asm_out = oracle_res["asm"]
            strategy = "hybrid_oracle_fallback"
        if asm_out is None:
            report["exit_code"] = int(JNCCExitCode.MODEL_FAILED)
            report["asm"] = None
            report["strategy_used"] = "hybrid_failed"
            return report
    else:
        report["exit_code"] = int(JNCCExitCode.INTERNAL)
        report["error"] = f"unknown backend {backend}"
        report["asm"] = None
        return report

    from compiler.jncc_peephole_asm import apply_peephole_asm

    asm_out = apply_peephole_asm(asm_out or "")
    report["stages"]["assemble"] = {}
    ok_a, msg_a = assemble_check(asm_out)
    report["stages"]["assemble"]["assemble_check"] = {"ok": ok_a, "msg": msg_a[:2000]}
    ok_s, msg_s = basic_asm_sanity(asm_out)
    report["stages"]["assemble"]["basic_sanity"] = {"ok": ok_s, "msg": msg_s}

    if not ok_a:
        report["exit_code"] = int(JNCCExitCode.ASSEMBLE_FAILED)
        report["asm"] = asm_out
        report["strategy_used"] = strategy
        return report
    if not ok_s:
        report["exit_code"] = int(JNCCExitCode.SANITY_FAILED)
        report["asm"] = asm_out
        report["strategy_used"] = strategy
        return report

    report["exit_code"] = int(JNCCExitCode.OK)
    report["asm"] = asm_out
    report["strategy_used"] = strategy

    if compare_oracle and oracle_res.get("ok") and oracle_res.get("asm"):
        from compiler.jncc_asm_norm import normalized_asm_diff

        diff = normalized_asm_diff(asm_out, oracle_res["asm"])
        report["stages"]["oracle_compare"] = diff

    if run_qemu:
        qe, qmsg = try_compile_and_qemu_exit_code(asm_out)
        report["stages"]["qemu"] = {"exit_code": qe, "msg": qmsg[:1000]}
        # 工具链缺失时仅记录，不覆盖 assemble 已成功时的 exit_code

    return report


def write_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
