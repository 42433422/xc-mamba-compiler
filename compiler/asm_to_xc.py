"""
RISC-V64 GNU 汇编 → XC 反编译（针对 xc_asm_oracle.RISCV64AsmOracle 的 lowering）。

- 变量名无法恢复，按槽偏移首次出现顺序命名为 v0, v1, …
- 非 Oracle 风格、call、RVV 等会触发 AsmDecompileUnsupported。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

Expr = Union[
    Tuple[str, int],
    Tuple[str, str],
    Tuple[str, str, "Expr"],
    Tuple[str, str, "Expr", "Expr"],
]


class AsmDecompileUnsupported(Exception):
    pass


@dataclass(frozen=True)
class _Insn:
    labels: Tuple[str, ...] = ()
    mnem: str = ""
    ops: Tuple[str, ...] = ()


def _parse_asm_lines(asm: str) -> List[_Insn]:
    out: List[_Insn] = []
    pending: List[str] = []
    for raw in asm.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if re.match(r"^[\w$.]+:\s*$", line) and not line.startswith("\t"):
            pending.append(line[:-1].strip())
            continue
        s = line.lstrip("\t").strip()
        if not s:
            continue
        parts = [p for p in re.sub(r",\s*", " ", s).split() if p]
        if not parts:
            continue
        mnem = parts[0].lower()
        ops = tuple(parts[1:])
        out.append(_Insn(labels=tuple(pending), mnem=mnem, ops=ops))
        pending = []
    if pending:
        out.append(_Insn(labels=tuple(pending), mnem="", ops=()))
    return out


def _label_index(insns: Sequence[_Insn]) -> Dict[str, int]:
    m: Dict[str, int] = {}
    for i, ins in enumerate(insns):
        for lb in ins.labels:
            m[lb] = i
    return m


def _parse_offset_s0(op: str) -> Optional[int]:
    m = re.match(r"^(-?\d+)\(s0\)$", op)
    return int(m.group(1)) if m else None


def _parse_offset_sp(op: str) -> Optional[int]:
    m = re.match(r"^(-?\d+)\(sp\)$", op)
    return int(m.group(1)) if m else None


def _imm(ops: Sequence[str], i: int) -> int:
    return int(ops[i], 0)


def _reg(ops: Sequence[str], i: int) -> str:
    return ops[i].lower()


def _find_main_region(insns: List[_Insn]) -> Tuple[int, int, str]:
    start = None
    for i, ins in enumerate(insns):
        if "main" in ins.labels:
            start = i
            break
    if start is None:
        raise AsmDecompileUnsupported("未找到 main")
    exit_lbl = ".L_exit_main"
    end = len(insns)
    for i in range(start, len(insns)):
        if exit_lbl in insns[i].labels:
            end = i
            break
    return start, end, exit_lbl


class _OracleDecompiler:
    def __init__(self, insns: List[_Insn], exit_lbl: str):
        self.insns = insns
        self.exit_lbl = exit_lbl
        self.labels = _label_index(insns)
        self.slots: Dict[int, str] = {}
        self._if_depth = 0

    def slot_name(self, off: int) -> str:
        if off not in self.slots:
            self.slots[off] = f"v{len(self.slots)}"
        return self.slots[off]

    def _req(self, ok: bool, msg: str) -> None:
        if not ok:
            raise AsmDecompileUnsupported(msg)

    def emit_expr(self, e: Expr) -> str:
        k = e[0]
        if k == "lit":
            return str(e[1])
        if k == "var":
            return e[1]
        if k == "un":
            op, x = e[1], e[2]
            inner = self.emit_expr(x)
            if op == "!":
                return f"!({inner})"
            if op == "-":
                return f"-{inner}" if inner.isalnum() else f"-({inner})"
            if op == "~":
                return f"~({inner})"
        if k == "bin":
            op, a, b = e[1], e[2], e[3]
            la, lb = self.emit_expr(a), self.emit_expr(b)
            if op in ("&&", "||", "==", "!=", "<", ">", "<=", ">="):
                return f"({la} {op} {lb})"
            return f"({la} {op} {lb})"
        raise AsmDecompileUnsupported("bad expr")

    def parse_atom(self, i: int, target: str) -> Tuple[Expr, int]:
        self._req(i < len(self.insns), "atom eof")
        ins = self.insns[i]
        if ins.mnem == "li" and len(ins.ops) == 2 and _reg(ins.ops, 0) == target:
            return ("lit", _imm(ins.ops, 1)), i + 1
        if ins.mnem == "lw" and len(ins.ops) == 2 and _reg(ins.ops, 0) == target:
            off = _parse_offset_s0(ins.ops[1])
            self._req(off is not None, "lw s0")
            return ("var", self.slot_name(off)), i + 1
        if ins.mnem == "call":
            raise AsmDecompileUnsupported("call 未支持")
        raise AsmDecompileUnsupported(f"atom {ins.mnem} {ins.ops}")

    def parse_unary_chain(self, i: int, target: str) -> Tuple[Expr, int]:
        e, j = self.parse_atom(i, target)
        while j < len(self.insns):
            ins = self.insns[j]
            if ins.mnem == "seqz" and len(ins.ops) == 2:
                if _reg(ins.ops, 0) == target and _reg(ins.ops, 1) == target:
                    e = ("un", "!", e)
                    j += 1
                    continue
            if (
                ins.mnem == "subw"
                and len(ins.ops) == 3
                and _reg(ins.ops, 0) == target
                and _reg(ins.ops, 1) == "zero"
                and _reg(ins.ops, 2) == target
            ):
                e = ("un", "-", e)
                j += 1
                continue
            if (
                ins.mnem == "xori"
                and len(ins.ops) == 3
                and _reg(ins.ops, 0) == target
                and _reg(ins.ops, 1) == target
                and _imm(ins.ops, 2) == -1
            ):
                e = ("un", "~", e)
                j += 1
                continue
            break
        return e, j

    def _combiner_len_and_op(self, k: int, target: str) -> Tuple[str, int]:
        """返回 (op, 从 k 起的指令条数)。"""
        self._req(k < len(self.insns), "combiner eof")
        ins = self.insns[k]
        o = ins.ops
        if ins.mnem == "addw" and len(o) == 3:
            self._req(
                _reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target,
                "addw",
            )
            return "+", 1
        if ins.mnem == "subw" and len(o) == 3 and _reg(o, 0) == "t1":
            self._req(_reg(o, 1) == "t0" and _reg(o, 2) == target, "subw t1")
            n1 = self.insns[k + 1]
            if n1.mnem == "seqz" and _reg(n1.ops, 0) == target and _reg(n1.ops, 1) == "t1":
                return "==", 2
            if n1.mnem == "snez" and _reg(n1.ops, 0) == target and _reg(n1.ops, 1) == "t1":
                return "!=", 2
            raise AsmDecompileUnsupported("subw t1 后缀")
        if ins.mnem == "subw" and len(o) == 3:
            self._req(_reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "subw")
            return "-", 1
        if ins.mnem == "mulw":
            self._req(len(o) == 3 and _reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "mulw")
            return "*", 1
        if ins.mnem == "divw":
            self._req(len(o) == 3 and _reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "divw")
            return "/", 1
        if ins.mnem == "remw":
            self._req(len(o) == 3 and _reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "remw")
            return "%", 1
        if ins.mnem == "slt" and len(o) == 3 and _reg(o, 0) == target:
            if _reg(o, 1) == "t0" and _reg(o, 2) == target:
                return "<", 1
            if _reg(o, 1) == target and _reg(o, 2) == "t0":
                return ">", 1
        if ins.mnem == "slt" and len(o) == 3 and _reg(o, 0) == "t1":
            if _reg(o, 1) == target and _reg(o, 2) == "t0":
                n1 = self.insns[k + 1]
                self._req(n1.mnem == "xori", "<= xori")
                return "<=", 2
            if _reg(o, 1) == "t0" and _reg(o, 2) == target:
                n1 = self.insns[k + 1]
                self._req(n1.mnem == "xori", ">= xori")
                return ">=", 2
        if ins.mnem == "and" and len(o) == 3:
            self._req(_reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "and")
            n1 = self.insns[k + 1]
            if n1.mnem == "snez":
                return "&&", 2
            return "&", 1
        if ins.mnem == "or" and len(o) == 3:
            self._req(_reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "or")
            n1 = self.insns[k + 1]
            if n1.mnem == "snez":
                return "||", 2
            return "|", 1
        if ins.mnem == "xor" and len(o) == 3:
            self._req(_reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "xor")
            return "^", 1
        if ins.mnem == "sllw":
            self._req(len(o) == 3 and _reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "sllw")
            return "<<", 1
        if ins.mnem == "sraw":
            self._req(len(o) == 3 and _reg(o, 0) == target and _reg(o, 1) == "t0" and _reg(o, 2) == target, "sraw")
            return ">>", 1
        raise AsmDecompileUnsupported(f"组合指令 {ins.mnem} {ins.ops}")

    def parse_subexpr(self, i: int, target: str) -> Tuple[Expr, int]:
        e, j = self.parse_unary_chain(i, target)
        while j < len(self.insns):
            ins = self.insns[j]
            if not (
                ins.mnem == "addi"
                and len(ins.ops) == 3
                and _reg(ins.ops, 0) == "sp"
                and _reg(ins.ops, 1) == "sp"
                and _imm(ins.ops, 2) == -16
            ):
                break
            ins1 = self.insns[j + 1]
            self._req(ins1.mnem == "sd" and len(ins1.ops) == 2, "binary sd")
            self._req(_reg(ins1.ops, 0) == target and _parse_offset_sp(ins1.ops[1]) == 8, "sd 8(sp)")
            e2, k = self.parse_subexpr(j + 2, target)
            self._req(k + 2 < len(self.insns), "binary tail")
            ld = self.insns[k]
            spu = self.insns[k + 1]
            self._req(ld.mnem == "ld" and _reg(ld.ops, 0) == "t0" and _parse_offset_sp(ld.ops[1]) == 8, "ld t0")
            self._req(
                spu.mnem == "addi"
                and _reg(spu.ops, 0) == "sp"
                and _reg(spu.ops, 1) == "sp"
                and _imm(spu.ops, 2) == 16,
                "sp+16",
            )
            op, clen = self._combiner_len_and_op(k + 2, target)
            e = ("bin", op, e, e2)
            j = k + 2 + clen
        return e, j

    def parse_subexpr_a0(self, i: int) -> Tuple[Expr, int]:
        return self.parse_subexpr(i, "a0")

    def _labels_here(self, i: int) -> Tuple[str, ...]:
        return self.insns[i].labels if i < len(self.insns) else ()

    def _has_label(self, i: int, lb: str) -> bool:
        return lb in self._labels_here(i)

    def _find_matching_endif(self, else_idx: int) -> int:
        """从 else 块首指令下标 else_idx 起，配对到闭合本层 if 的 .endif_ 标签行。"""
        pos = else_idx + 1
        depth = 1
        while pos < len(self.insns):
            ins = self.insns[pos]
            if ins.mnem == "beqz" and len(ins.ops) == 2 and _reg(ins.ops, 0) == "a0":
                depth += 1
            for lb in ins.labels:
                if lb.startswith(".endif_"):
                    depth -= 1
            if depth <= 0:
                return pos
            pos += 1
        raise AsmDecompileUnsupported("未找到 endif")

    def parse_stmt_list(self, i: int, stop_labels: frozenset[str]) -> Tuple[List[str], int]:
        lines: List[str] = []
        while i < len(self.insns):
            if self.exit_lbl in self._labels_here(i):
                return lines, i
            ins0 = self.insns[i]
            if (
                ins0.mnem == "li"
                and not ins0.labels
                and i + 1 < len(self.insns)
                and self.exit_lbl in self.insns[i + 1].labels
            ):
                i += 1
                continue
            for sl in stop_labels:
                if sl in self._labels_here(i):
                    return lines, i
            ins = self.insns[i]
            if ins.mnem == "" and not ins.labels:
                i += 1
                continue
            if ins.labels:
                lb0 = ins.labels[0]
                if lb0.startswith(".w_beg_"):
                    bl, i = self._parse_while(i)
                    lines.extend(bl)
                    continue
                if lb0.startswith(".f_beg_"):
                    bl, i = self._parse_for(i)
                    lines.extend(bl)
                    continue
            if ins.mnem == "j" and len(ins.ops) == 1:
                t = ins.ops[0]
                if t == self.exit_lbl:
                    i += 1
                    if i < len(self.insns) and self.insns[i].mnem == "li":
                        n2 = i + 1
                        if n2 < len(self.insns) and self.insns[n2].labels:
                            lbs = self.insns[n2].labels
                            if any(
                                x.startswith(".else_") or x.startswith(".endif_") for x in lbs
                            ):
                                i += 1
                    continue
                if t.startswith(".endif_"):
                    i += 1
                    continue
                if t.startswith(".w_end_") or t.startswith(".f_end_"):
                    lines.append("    break")
                    i += 1
                    continue
                if t.startswith(".w_beg_") or t.startswith(".f_beg_"):
                    lines.append("    continue")
                    i += 1
                    continue
            if ins.mnem == "sw" and len(ins.ops) == 2 and ins.ops[0] == "zero":
                off = _parse_offset_s0(ins.ops[1])
                self._req(off is not None, "sw zero")
                vn = self.slot_name(off)
                lines.append(f"    ${vn}: int = 0")
                i += 1
                continue
            if (
                i + 2 < len(self.insns)
                and self.insns[i].mnem == "li"
                and len(self.insns[i].ops) == 2
                and _reg(self.insns[i].ops, 0) == "a0"
                and self.insns[i + 1].mnem == "sw"
                and len(self.insns[i + 1].ops) == 2
                and _reg(self.insns[i + 1].ops, 0) == "a0"
                and _parse_offset_s0(self.insns[i + 1].ops[1]) is not None
            ):
                nxt = self.insns[i + 2]
                if any(lb.startswith(".f_beg_") for lb in nxt.labels):
                    bl, i = self._parse_for(i + 2)
                    lines.extend(bl)
                    continue
            if (
                i + 2 < len(self.insns)
                and self.insns[i].mnem == "lw"
                and len(self.insns[i].ops) == 2
                and _reg(self.insns[i].ops, 0) == "a0"
            ):
                off_inc = _parse_offset_s0(self.insns[i].ops[1])
                if off_inc is not None:
                    n1, n2 = self.insns[i + 1], self.insns[i + 2]
                    if (
                        n1.mnem in ("addiw", "addi")
                        and len(n1.ops) == 3
                        and _reg(n1.ops, 0) == "a0"
                        and _reg(n1.ops, 1) == "a0"
                        and n2.mnem == "sw"
                        and len(n2.ops) == 2
                        and _reg(n2.ops, 0) == "a0"
                        and _parse_offset_s0(n2.ops[1]) == off_inc
                    ):
                        d = _imm(n1.ops, 2)
                        vn = self.slot_name(off_inc)
                        if d == 1:
                            lines.append(f"    ${vn}++")
                            i += 3
                            continue
                        if d == -1:
                            lines.append(f"    ${vn}--")
                            i += 3
                            continue
            e, j = self.parse_subexpr_a0(i)
            nxt = self.insns[j] if j < len(self.insns) else None
            self._req(nxt is not None, "stmt 截断")
            if nxt.mnem == "sw" and len(nxt.ops) == 2 and _reg(nxt.ops, 0) == "a0":
                off = _parse_offset_s0(nxt.ops[1])
                self._req(off is not None, "sw s0")
                vn = self.slot_name(off)
                lines.append(f"    ${vn}: int = {self.emit_expr(e)}")
                i = j + 1
                continue
            if nxt.mnem == "beqz":
                bl, i = self._parse_if(i)
                lines.extend(bl)
                if self._if_depth == 0:
                    while i < len(self.insns) and self._dead_endif_li(self.insns[i]):
                        i += 1
                continue
            if nxt.mnem == "j" and nxt.ops[0] == self.exit_lbl:
                lines.append(f"    ^ {self.emit_expr(e)}")
                i = j + 1
                if (
                    i < len(self.insns)
                    and self.insns[i].mnem == "li"
                    and not self.insns[i].labels
                ):
                    i += 1
                continue
            raise AsmDecompileUnsupported(f"无法识别语句 @{i}: {nxt.mnem} {nxt.ops}")
        return lines, i

    def _parse_if(self, start: int) -> Tuple[List[str], int]:
        self._if_depth += 1
        try:
            e, j = self.parse_subexpr_a0(start)
            ins = self.insns[j]
            self._req(ins.mnem == "beqz" and _reg(ins.ops, 0) == "a0", "if beqz")
            else_l = ins.ops[1]
            ei = self.labels.get(else_l)
            self._req(ei is not None, f"else 标签 {else_l}")
            then_lines, mid = self.parse_stmt_list(j + 1, frozenset({else_l}))
            self._req(mid == ei, "then 边界")
            endif_i = self._find_matching_endif(ei)
            end_labs = frozenset(self.insns[endif_i].labels) | frozenset({self.exit_lbl})
            # .else 标签与首条可执行指令可能在同一 _Insn（如 .else:\n\tli）
            else_lines, after = self.parse_stmt_list(ei, end_labs)
            self._req(after == endif_i, "else 边界")
            cstr = self.emit_expr(e)
            out = [f"    ? {cstr} {{"]
            out.extend(then_lines)
            out.append("    } ?: {")
            out.extend(else_lines)
            out.append("    }")
            return out, endif_i
        finally:
            self._if_depth -= 1

    def _dead_endif_li(self, ins: _Insn) -> bool:
        if not ins.labels or not any(x.startswith(".endif_") for x in ins.labels):
            return False
        return (
            ins.mnem == "li"
            and len(ins.ops) == 2
            and _reg(ins.ops, 0) == "a0"
            and _imm(ins.ops, 1) == 0
        )

    def _parse_while(self, start: int) -> Tuple[List[str], int]:
        self._req(start < len(self.insns), "while")
        lab = self.insns[start].labels[0]
        self._req(lab.startswith(".w_beg_"), "w_beg")
        cond_i = start if self.insns[start].mnem else start + 1
        e, j = self.parse_subexpr_a0(cond_i)
        ins = self.insns[j]
        self._req(ins.mnem == "beqz", "while beqz")
        end_l = ins.ops[1]
        body, k = self.parse_stmt_list(j + 1, frozenset({end_l}))
        self._req(k < len(self.insns) and end_l in self.insns[k].labels, "w_end")
        back = k - 1
        self._req(
            back >= 0 and self.insns[back].mnem == "j" and self.insns[back].ops[0] == lab,
            "while 回边",
        )
        while body and body[-1].strip() == "continue":
            body.pop()
        lines = [f"    while {self.emit_expr(e)} {{"]
        lines.extend(body)
        lines.append("    }")
        return lines, k

    def _parse_for(self, start: int) -> Tuple[List[str], int]:
        lab = self.insns[start].labels[0]
        self._req(lab.startswith(".f_beg_"), "f_beg")
        cond_i = start if self.insns[start].mnem else start + 1
        e, j = self.parse_subexpr_a0(cond_i)
        ins = self.insns[j]
        self._req(ins.mnem == "beqz", "for beqz")
        end_l = ins.ops[1]
        body, k = self.parse_stmt_list(j + 1, frozenset({end_l}))
        self._req(k < len(self.insns) and end_l in self.insns[k].labels, "f_end")
        vn0, init_lit = "v0", 0
        if start >= 2:
            p0, p1 = self.insns[start - 2], self.insns[start - 1]
            if (
                p0.mnem == "li"
                and len(p0.ops) == 2
                and _reg(p0.ops, 0) == "a0"
                and p1.mnem == "sw"
                and len(p1.ops) == 2
                and _reg(p1.ops, 0) == "a0"
            ):
                o0 = _parse_offset_s0(p1.ops[1])
                if o0 is not None:
                    vn0 = self.slot_name(o0)
                    init_lit = _imm(p0.ops, 1)
        hdr = f"    ~{vn0}: int = {init_lit}; {self.emit_expr(e)}; {vn0}++ {{"
        inc_pat = f"${vn0}++"
        body = [ln for ln in body if ln.strip() != inc_pat]
        while body and body[-1].strip() == "continue":
            body.pop()
        lines = [hdr, *body, "    }"]
        return lines, k


def decompile_oracle_asm_to_xc(asm: str) -> str:
    all_ins = _parse_asm_lines(asm)
    s0, e0, exit_lbl = _find_main_region(all_ins)
    body = all_ins[s0 : e0 + 1]
    dc = _OracleDecompiler(body, exit_lbl)
    i = 0
    while i < len(body) and not ("main" in body[i].labels and body[i].mnem == "addi"):
        i += 1
    dc._req(i < len(body), "main addi")
    i += 1
    while i < len(body):
        ins = body[i]
        if ins.mnem == "sd" and len(ins.ops) == 2:
            i += 1
            continue
        if ins.mnem == "mv" and len(ins.ops) == 2 and _reg(ins.ops, 0) == "s0" and _reg(ins.ops, 1) == "sp":
            i += 1
            break
        i += 1
    else:
        raise AsmDecompileUnsupported("缺少 mv s0,sp")
    stmts, _ = dc.parse_stmt_list(i, frozenset())
    return "\n".join(["# {", *stmts, "}"]) + "\n"
