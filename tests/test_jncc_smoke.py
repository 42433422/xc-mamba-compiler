from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_ir_constant_fold_roundtrip():
    from compiler.jncc_ir_v0 import compile_xc_via_ir

    xc = "# {\n    $x: int = 2 + 3\n    ^ x\n}\n"
    r = compile_xc_via_ir(xc, optimize=True)
    assert r["ok"], r
    assert "li\ta0, 5" in (r.get("asm") or "")


def test_jncc_pipeline_oracle():
    from compiler.jncc_pipeline import run_compile

    r = run_compile("# {\n$x: int = 1\n^ x\n}\n", backend="oracle")
    assert r["exit_code"] == 0
    assert r.get("asm")


def test_normalize_asm_diff_self():
    from compiler.jncc_asm_norm import normalized_asm_diff

    s = "\t.text\n\t.globl\tmain\nmain:\n\tret\n"
    d = normalized_asm_diff(s, s)
    assert d["equal_normalized"]


def test_classify_compiler_outcome():
    from compiler.jncc_eval_metrics import classify_compiler_outcome

    assert (
        classify_compiler_outcome(parse_ok=False, pred_asm="", gold_asm="x") == "E1_parse_fail"
    )
    assert classify_compiler_outcome(parse_ok=True, pred_asm="", gold_asm="") == "E2_model_empty_output"


def test_simplify_algebra():
    from compiler.jncc_ir_opt import simplify_algebra_ir

    ir = {
        "k": "Program",
        "body": [
            {
                "k": "ReturnStmt",
                "value": {
                    "k": "BinaryOp",
                    "op": "+",
                    "left": {"k": "Identifier", "name": "x"},
                    "right": {"k": "NumberLiteral", "value": 0},
                },
            }
        ],
    }
    out = simplify_algebra_ir(ir)
    assert out["body"][0]["value"]["k"] == "Identifier"
