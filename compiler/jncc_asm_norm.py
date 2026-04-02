"""汇编规范化与弱等价比较（对拍用）。"""

from __future__ import annotations

import re
from typing import Any, Dict


def normalize_asm_lines(asm: str) -> str:
    out: list[str] = []
    for ln in asm.splitlines():
        s = ln.split("#")[0].strip()
        if not s:
            continue
        s = re.sub(r"\s+", " ", s)
        out.append(s)
    return "\n".join(out)


def normalized_asm_diff(pred: str, gold: str) -> Dict[str, Any]:
    np = normalize_asm_lines(pred)
    ng = normalize_asm_lines(gold)
    return {
        "equal_normalized": np == ng,
        "norm_len_pred": len(np),
        "norm_len_gold": len(ng),
        "line_count_pred": len(np.splitlines()),
        "line_count_gold": len(ng.splitlines()),
    }
