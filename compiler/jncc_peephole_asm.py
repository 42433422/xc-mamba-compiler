"""RISC-V GNU 汇编窥孔（纯文本规则，不保证语义保留时保守跳过）。"""

from __future__ import annotations

import re


def apply_peephole_asm(asm: str) -> str:
    lines = asm.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        # 删除连续相同的 mv r,r
        m = re.match(r"^(\s*)mv\s+([a-z0-9]+),\s*\2\s*$", ln, re.I)
        if m:
            i += 1
            continue
        # li r, 0 -> 可用 mv r, zero，但可能更长；跳过
        out.append(ln)
        i += 1
    return "\n".join(out) + ("\n" if asm.strip() else "")
