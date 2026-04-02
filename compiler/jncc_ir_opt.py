"""IR v0 额外代数化简（在常量折叠之后应用）。"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional


def _simplify_expr(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if d is None:
        return None
    k = d.get("k")
    if k == "BinaryOp":
        left = _simplify_expr(d["left"])
        right = _simplify_expr(d["right"])
        op = d["op"]
        if right and right.get("k") == "NumberLiteral":
            v = int(right["value"])
            if op == "+" and v == 0:
                return left
            if op == "-" and v == 0 and left:
                return left
            if op == "*" and v == 1:
                return left
            if op == "*" and v == 0 and left:
                return right
        if left and left.get("k") == "NumberLiteral":
            v = int(left["value"])
            if op == "+" and v == 0 and right:
                return right
            if op == "*" and v == 0 and right:
                return left
            if op == "*" and v == 1 and right:
                return right
        return {**d, "left": left, "right": right}
    if k == "UnaryOp":
        return {**d, "operand": _simplify_expr(d["operand"])}
    if k == "Call":
        return {**d, "args": [_simplify_expr(a) for a in d.get("args", [])]}
    return d


def _simplify_stmt(d: Dict[str, Any]) -> Dict[str, Any]:
    k = d["k"]
    if k == "VarDecl":
        return {**d, "value": _simplify_expr(d.get("value"))}
    if k == "IfStmt":
        return {
            **d,
            "condition": _simplify_expr(d["condition"]),
            "then_body": [_simplify_stmt(x) for x in d["then_body"]],
            "else_body": [_simplify_stmt(x) for x in d["else_body"]] if d.get("else_body") else None,
            "else_if": _simplify_stmt(d["else_if"]) if d.get("else_if") else None,
        }
    if k == "WhileStmt":
        return {
            **d,
            "condition": _simplify_expr(d["condition"]),
            "body": [_simplify_stmt(x) for x in d["body"]],
        }
    if k == "ForStmt":
        return {
            **d,
            "init": _simplify_stmt(d["init"]) if d.get("init") else None,
            "condition": _simplify_expr(d.get("condition")) if d.get("condition") else None,
            "update": _simplify_stmt(d["update"]) if d.get("update") else None,
            "body": [_simplify_stmt(x) for x in d["body"]],
        }
    if k == "ReturnStmt":
        return {**d, "value": _simplify_expr(d.get("value"))}
    if k == "FuncDef":
        return {**d, "body": [_simplify_stmt(x) for x in d["body"]]}
    return d


def simplify_algebra_ir(ir: Dict[str, Any]) -> Dict[str, Any]:
    ir = copy.deepcopy(ir)
    if ir.get("k") != "Program":
        raise ValueError("IR root must be Program")
    ir["body"] = [_simplify_stmt(x) for x in ir["body"]]
    return ir
