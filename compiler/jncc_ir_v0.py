"""
JNCC IR v0：JSON 可序列化的程序树（镜像 XC AST 子集）+ 常量折叠 + 还原 XC 源码，
再调用 Oracle 生成汇编（严格路线下不引入 gcc/llvm）。
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from xc_asm_oracle import compile_xc_to_asm_riscv64_with_reason, parse_xc_program
from xc_compiler import (
    ASTNode,
    BinaryOp,
    BoolLiteral,
    BreakStmt,
    Call,
    ContinueStmt,
    ForStmt,
    FuncDef,
    Identifier,
    IfStmt,
    NumberLiteral,
    Program,
    ReturnStmt,
    UnaryOp,
    VarDecl,
    WhileStmt,
)


def ast_to_ir_v0(node: ASTNode) -> Dict[str, Any]:
    """将 AST 转为 JSON-serializable dict（带键 k）。"""
    if isinstance(node, Program):
        return {"k": "Program", "body": [ast_to_ir_v0(x) for x in node.body]}
    if isinstance(node, VarDecl):
        return {
            "k": "VarDecl",
            "name": node.name,
            "var_type": node.var_type,
            "value": ast_to_ir_v0(node.value) if node.value else None,
            "is_const": node.is_const,
        }
    if isinstance(node, FuncDef):
        return {
            "k": "FuncDef",
            "name": node.name,
            "params": [[a, b] for a, b in node.params],
            "return_type": node.return_type,
            "body": [ast_to_ir_v0(x) for x in node.body],
        }
    if isinstance(node, IfStmt):
        return {
            "k": "IfStmt",
            "condition": ast_to_ir_v0(node.condition),
            "then_body": [ast_to_ir_v0(x) for x in node.then_body],
            "else_body": [ast_to_ir_v0(x) for x in node.else_body] if node.else_body else None,
            "else_if": ast_to_ir_v0(node.else_if) if node.else_if else None,
        }
    if isinstance(node, WhileStmt):
        return {
            "k": "WhileStmt",
            "condition": ast_to_ir_v0(node.condition),
            "body": [ast_to_ir_v0(x) for x in node.body],
        }
    if isinstance(node, ForStmt):
        return {
            "k": "ForStmt",
            "init": ast_to_ir_v0(node.init) if node.init else None,
            "condition": ast_to_ir_v0(node.condition) if node.condition else None,
            "update": ast_to_ir_v0(node.update) if node.update else None,
            "body": [ast_to_ir_v0(x) for x in node.body],
        }
    if isinstance(node, ReturnStmt):
        return {
            "k": "ReturnStmt",
            "value": ast_to_ir_v0(node.value) if node.value else None,
        }
    if isinstance(node, BreakStmt):
        return {"k": "BreakStmt"}
    if isinstance(node, ContinueStmt):
        return {"k": "ContinueStmt"}
    if isinstance(node, Call):
        return {
            "k": "Call",
            "name": node.name,
            "args": [ast_to_ir_v0(a) for a in node.args],
        }
    if isinstance(node, NumberLiteral):
        return {"k": "NumberLiteral", "value": int(node.value)}
    if isinstance(node, BoolLiteral):
        return {"k": "BoolLiteral", "value": bool(node.value)}
    if isinstance(node, Identifier):
        return {"k": "Identifier", "name": node.name}
    if isinstance(node, UnaryOp):
        return {"k": "UnaryOp", "op": node.op, "operand": ast_to_ir_v0(node.operand)}
    if isinstance(node, BinaryOp):
        return {
            "k": "BinaryOp",
            "op": node.op,
            "left": ast_to_ir_v0(node.left),
            "right": ast_to_ir_v0(node.right),
        }
    raise TypeError(f"IR v0 unsupported AST: {type(node).__name__}")


def _fold_expr(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if d is None:
        return None
    k = d.get("k")
    if k == "BinaryOp":
        left = _fold_expr(d["left"])
        right = _fold_expr(d["right"])
        d = {**d, "left": left, "right": right}
        if left and right and left.get("k") == "NumberLiteral" and right.get("k") == "NumberLiteral":
            a, b = int(left["value"]), int(right["value"])
            op = d["op"]
            try:
                if op == "+":
                    v = a + b
                elif op == "-":
                    v = a - b
                elif op == "*":
                    v = a * b
                elif op == "/":
                    v = a // b if b != 0 else None
                elif op == "%":
                    v = a % b if b != 0 else None
                elif op == "==":
                    v = int(a == b)
                elif op == "!=":
                    v = int(a != b)
                elif op == "<":
                    v = int(a < b)
                elif op == ">":
                    v = int(a > b)
                elif op == "<=":
                    v = int(a <= b)
                elif op == ">=":
                    v = int(a >= b)
                elif op == "&":
                    v = a & b
                elif op == "|":
                    v = a | b
                elif op == "^":
                    v = a ^ b
                elif op == "<<":
                    v = a << b
                elif op == ">>":
                    v = a >> b
                else:
                    v = None
                if v is not None:
                    return {"k": "NumberLiteral", "value": int(v)}
            except Exception:
                pass
        return d
    if k == "UnaryOp":
        op = d["op"]
        sub = _fold_expr(d["operand"])
        d = {**d, "operand": sub}
        if sub and sub.get("k") == "NumberLiteral":
            a = int(sub["value"])
            if op == "-":
                return {"k": "NumberLiteral", "value": int(-a)}
            if op == "!":
                return {"k": "NumberLiteral", "value": int(not a)}
            if op == "~":
                return {"k": "NumberLiteral", "value": int(~a)}
        return d
    if k in ("NumberLiteral", "BoolLiteral", "Identifier"):
        return d
    if k == "Call":
        return {**d, "args": [_fold_expr(x) for x in d.get("args", [])]}
    return d


def _fold_stmt(d: Dict[str, Any]) -> Dict[str, Any]:
    k = d["k"]
    if k == "VarDecl":
        return {**d, "value": _fold_expr(d.get("value"))}
    if k == "IfStmt":
        return {
            **d,
            "condition": _fold_expr(d["condition"]),
            "then_body": [_fold_stmt(x) for x in d["then_body"]],
            "else_body": [_fold_stmt(x) for x in d["else_body"]] if d.get("else_body") else None,
            "else_if": _fold_stmt(d["else_if"]) if d.get("else_if") else None,
        }
    if k == "WhileStmt":
        return {
            **d,
            "condition": _fold_expr(d["condition"]),
            "body": [_fold_stmt(x) for x in d["body"]],
        }
    if k == "ForStmt":
        return {
            **d,
            "init": _fold_stmt(d["init"]) if d.get("init") else None,
            "condition": _fold_expr(d.get("condition")) if d.get("condition") else None,
            "update": _fold_stmt(d["update"]) if d.get("update") else None,
            "body": [_fold_stmt(x) for x in d["body"]],
        }
    if k == "ReturnStmt":
        return {**d, "value": _fold_expr(d.get("value"))}
    if k == "FuncDef":
        return {**d, "body": [_fold_stmt(x) for x in d["body"]]}
    return d


def fold_constants_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    ir = copy.deepcopy(ir)
    if ir.get("k") != "Program":
        raise ValueError("IR root must be Program")
    ir["body"] = [_fold_stmt(x) for x in ir["body"]]
    return ir


def prune_unreachable_linear(stmts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for st in stmts:
        out.append(st)
        if st.get("k") == "ReturnStmt":
            break
    return out


def prune_unreachable_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    ir = copy.deepcopy(ir)

    def walk_block(stmts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        res: List[Dict[str, Any]] = []
        for st in stmts:
            st = prune_stmt(st)
            res.append(st)
            if st.get("k") == "ReturnStmt":
                break
        return res

    def prune_stmt(st: Dict[str, Any]) -> Dict[str, Any]:
        sk = st.get("k")
        if sk == "IfStmt":
            return {
                **st,
                "then_body": walk_block(st["then_body"]),
                "else_body": walk_block(st["else_body"]) if st.get("else_body") else None,
                "else_if": prune_stmt(st["else_if"]) if st.get("else_if") else None,
            }
        if sk == "WhileStmt":
            return {**st, "body": walk_block(st["body"])}
        if sk == "ForStmt":
            return {**st, "body": walk_block(st["body"])}
        if sk == "FuncDef":
            return {**st, "body": walk_block(st["body"])}
        return st

    if ir.get("k") == "Program":
        ir["body"] = walk_block(ir["body"])
    return ir


def _emit_if_chain_xc(d: Dict[str, Any], indent: str, *, is_first: bool) -> List[str]:
    head = "? " if is_first else "?? "
    lines: List[str] = [f"{indent}{head}({expr_to_xc(d['condition'])}) {{"]
    for s in d["then_body"]:
        lines.extend(stmt_to_xc_lines(s, indent + "    "))
    lines.append(f"{indent}}}")
    if d.get("else_if"):
        lines.extend(_emit_if_chain_xc(d["else_if"], indent, is_first=False))
    elif d.get("else_body"):
        lines.append(f"{indent}?: {{")
        for s in d["else_body"]:
            lines.extend(stmt_to_xc_lines(s, indent + "    "))
        lines.append(f"{indent}}}")
    return lines


def expr_to_xc(d: Dict[str, Any]) -> str:
    k = d["k"]
    if k == "NumberLiteral":
        return str(int(d["value"]))
    if k == "BoolLiteral":
        return "true" if d["value"] else "false"
    if k == "Identifier":
        return d["name"]
    if k == "UnaryOp":
        op = d["op"]
        inner = expr_to_xc(d["operand"])
        if op == "++post":
            return f"{inner}++"
        if op == "--post":
            return f"{inner}--"
        if op == "!":
            return f"!({inner})"
        if op == "~":
            return f"~({inner})"
        if op == "-":
            if d["operand"].get("k") == "NumberLiteral":
                return str(-int(d["operand"]["value"]))
            return f"-({inner})"
        return f"{op}({inner})"
    if k == "BinaryOp":
        return f"({expr_to_xc(d['left'])} {d['op']} {expr_to_xc(d['right'])})"
    if k == "Call":
        args = ", ".join(expr_to_xc(a) for a in d.get("args", []))
        return f"{d['name']}({args})"
    raise ValueError(f"expr_to_xc: {k}")


def stmt_to_xc_lines(d: Dict[str, Any], indent: str = "    ") -> List[str]:
    k = d["k"]
    lines: List[str] = []
    if k == "VarDecl":
        t = d.get("var_type")
        name = d["name"]
        if d.get("is_const"):
            val = expr_to_xc(d["value"]) if d.get("value") else "0"
            lines.append(f"{indent}@{name} = {val}")
        elif t:
            val = expr_to_xc(d["value"]) if d.get("value") else ""
            lines.append(f"{indent}${name}: {t} = {val}" if val else f"{indent}${name}: {t}")
        else:
            val = expr_to_xc(d["value"]) if d.get("value") else "0"
            lines.append(f"{indent}${name} = {val}")
        return lines
    if k == "ReturnStmt":
        if d.get("value"):
            lines.append(f"{indent}^{expr_to_xc(d['value'])}")
        else:
            lines.append(f"{indent}^ 0")
        return lines
    if k == "BreakStmt":
        lines.append(f"{indent}>")
        return lines
    if k == "ContinueStmt":
        lines.append(f"{indent}<")
        return lines
    if k == "IfStmt":
        lines.extend(_emit_if_chain_xc(d, indent, is_first=True))
        return lines
    if k == "WhileStmt":
        lines.append(f"{indent}@ ({expr_to_xc(d['condition'])}) {{")
        for s in d["body"]:
            lines.extend(stmt_to_xc_lines(s, indent + "    "))
        lines.append(f"{indent}}}")
        return lines
    if k == "ForStmt":
        init_s = ""
        if d.get("init"):
            ini = d["init"]
            if ini.get("k") == "VarDecl":
                t = ini.get("var_type")
                if t:
                    init_s = f"${ini['name']}: {t} = {expr_to_xc(ini['value'])}" if ini.get("value") else f"${ini['name']}: {t}"
                elif ini.get("value"):
                    init_s = f"${ini['name']} = {expr_to_xc(ini['value'])}"
                else:
                    init_s = f"${ini['name']}"
            else:
                init_s = expr_to_xc(ini)
        cond_s = expr_to_xc(d["condition"]) if d.get("condition") else ""
        upd_s = ""
        if d.get("update"):
            u = d["update"]
            if u.get("k") == "VarDecl" and u.get("value"):
                upd_s = f"{u['name']} = {expr_to_xc(u['value'])}"
            else:
                upd_s = expr_to_xc(u)
        mid = "; ".join(x for x in (init_s, cond_s, upd_s) if x)
        hdr = f"~{mid}" if mid else "~"
        lines.append(f"{indent}{hdr} {{")
        for s in d["body"]:
            lines.extend(stmt_to_xc_lines(s, indent + "    "))
        lines.append(f"{indent}}}")
        return lines
    if k == "Call":
        lines.append(f"{indent}{expr_to_xc(d)}")
        return lines
    if k == "FuncDef":
        ps = ", ".join(f"{n}: {t}" for n, t in d["params"])
        rt = d.get("return_type") or "int"
        lines.append(f"{indent}% {d['name']}({ps}) -> {rt} {{")
        for s in d["body"]:
            lines.extend(stmt_to_xc_lines(s, indent + "    "))
        lines.append(f"{indent}}}")
        return lines
    raise ValueError(f"stmt_to_xc_lines: {k}")


def ir_to_xc_program(ir: Dict[str, Any]) -> str:
    if ir.get("k") != "Program":
        raise ValueError("root must be Program")
    parts: List[str] = ["# {"]
    for st in ir["body"]:
        parts.extend(stmt_to_xc_lines(st, "    "))
    parts.append("}")
    return "\n".join(parts) + "\n"


def compile_xc_via_ir(xc_source: str, *, optimize: bool = True) -> Dict[str, Any]:
    try:
        prog = parse_xc_program(xc_source)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "asm": None, "error": f"parse:{e}", "meta": {}}

    ir = ast_to_ir_v0(prog)
    if optimize:
        ir = fold_constants_ir(ir)
        from compiler.jncc_ir_opt import simplify_algebra_ir

        ir = simplify_algebra_ir(ir)
        ir = prune_unreachable_ir(ir)
    try:
        xc2 = ir_to_xc_program(ir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "asm": None, "error": f"ir_to_xc:{e}", "meta": {"ir": ir}}

    res = compile_xc_to_asm_riscv64_with_reason(xc2)
    return {
        "ok": res["ok"],
        "asm": res.get("asm"),
        "error": res.get("unsupported_reason"),
        "meta": {
            "xc_lowered": xc2,
            "ir_json": json.dumps(ir, ensure_ascii=False)[:8000],
            "ir_version": 0,
        },
    }


def ir_schema_v0() -> Dict[str, Any]:
    return {
        "version": 0,
        "root": "Program",
        "node_kinds": [
            "Program",
            "VarDecl",
            "FuncDef",
            "IfStmt",
            "WhileStmt",
            "ForStmt",
            "ReturnStmt",
            "BreakStmt",
            "ContinueStmt",
            "Call",
            "NumberLiteral",
            "BoolLiteral",
            "Identifier",
            "UnaryOp",
            "BinaryOp",
        ],
        "notes": "Serialized XC AST subset; lowered XC is recompiled by Oracle.",
    }
