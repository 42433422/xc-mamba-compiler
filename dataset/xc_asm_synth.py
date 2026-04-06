"""
生成 XC 程序样本（含 feature tags / difficulty），用于大规模 XC↔ASM 数据工厂。
递归、大规模线性链、扁平「高维」槽位、工业状态机/CRC 风格等金标见 build_complex_xc_supplement.py。
"""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Tuple


def gen_simple_arith(rng: random.Random) -> str:
    a, b, c = rng.randint(0, 50), rng.randint(0, 50), rng.randint(0, 20)
    op = rng.choice(["+", "-", "*"])
    return f"""# {{
    $x: int = {a}
    $y: int = {b}
    $z: int = x {op} y {op} {c}
    ^ z
}}"""


def gen_if_else(rng: random.Random) -> str:
    a, b = rng.randint(0, 30), rng.randint(0, 30)
    return f"""# {{
    $a: int = {a}
    $b: int = {b}
    $r: int = 0
    ? (a > b) {{
        $r: int = 1
    }} ?: {{
        $r: int = 2
    }}
    ^ r
}}"""


def gen_while_sum(rng: random.Random) -> str:
    n = rng.randint(1, 8)
    return f"""# {{
    $i: int = {n}
    $s: int = 0
    while (i > 0) {{
        $s: int = s + i
        $i: int = i - 1
    }}
    ^ s
}}"""


def gen_for_loop(rng: random.Random) -> str:
    hi = rng.randint(3, 10)
    return f"""# {{
    ~j: int = 0; j < {hi}; j++ {{
        $acc: int = j
    }}
    ^ j
}}"""


def gen_func_call(rng: random.Random) -> str:
    k = rng.randint(1, 12)
    return f"""# {{
    % mul2(t: int) -> int {{
        ^ t * 2
    }}
    $v: int = {k}
    $w: int = mul2(v)
    ^ w + 1
}}"""


def gen_compare_chain(rng: random.Random) -> str:
    x, y = rng.randint(0, 15), rng.randint(0, 15)
    return f"""# {{
    $x: int = {x}
    $y: int = {y}
    ? ((x == y)) {{
        ^ 100
    }} ?: {{
        ? ((x < y)) {{
            ^ 200
        }} ?: {{
            ^ 300
        }}
    }}
}}"""


def gen_pointer_malloc(rng: random.Random) -> str:
    n = rng.randint(1, 8)
    return f"""# {{
    $n: int = {n}
    $p: *int = ΩM(4 * n)
    ^ n
}}"""


def gen_string_lib(rng: random.Random) -> str:
    return """# {
    $a: string = "abc"
    $b: string = "abd"
    $x: int = strcmp(a, b)
    ^ x
}"""


def gen_file_io(rng: random.Random) -> str:
    return """# {
    $f: int = fopen("a.bin", "rb")
    $ok: int = 1
    ^ ok
}"""


def gen_switch_case(rng: random.Random) -> str:
    v = rng.randint(0, 3)
    return f"""# {{
    $x: int = {v}
    $r: int = 0
    ?▶ (x) {{
        #C 0:
            $r: int = 10
            >;
        #C 1:
            $r: int = 20
            >;
        #J:
            $r: int = 30
    }}
    ^ r
}}"""


def gen_array_simulated(rng: random.Random) -> str:
    """固定槽位模拟小数组（无指针/IndexAccess），Oracle 可编译。"""
    n = rng.randint(2, 5)
    vals = [rng.randint(0, 4) for _ in range(n)]
    lines = ["# {"]
    for i, v in enumerate(vals):
        lines.append(f"    $a{i}: int = {v}")
    last = " + ".join(f"a{i}" for i in range(n))
    lines.append(f"    ^ {last}")
    lines.append("}")
    return "\n".join(lines)


def gen_union_bitfield_fnptr(rng: random.Random) -> str:
    # 这类特性先用预处理桥接，语法可生成，后端可能不支持（用于 unsupported_reason 统计）
    return """⟨R union U { int i; float f; };
⟨R struct BF { unsigned a:3; unsigned b:5; };
⟨T int (*fn_t)(int);
# {
    $x: int = 7
    ^ x
}"""


GENERATOR_SPECS: List[Tuple[Callable[[random.Random], str], List[str], str]] = [
    (gen_simple_arith, ["arith"], "easy"),
    (gen_if_else, ["if"], "easy"),
    (gen_while_sum, ["while"], "easy"),
    (gen_for_loop, ["for"], "easy"),
    (gen_array_simulated, ["array_sim", "multi_slot"], "easy"),
    (gen_func_call, ["func_call"], "medium"),
    (gen_compare_chain, ["if", "compare"], "medium"),
    (gen_pointer_malloc, ["pointer", "malloc"], "medium"),
    (gen_string_lib, ["string_lib"], "medium"),
    (gen_file_io, ["file_io"], "hard"),
    (gen_switch_case, ["switch"], "hard"),
    (gen_union_bitfield_fnptr, ["union", "bitfield", "fnptr_typedef"], "hard"),
]


def generate_one_with_meta(rng: random.Random) -> Dict:
    g, tags, level = rng.choice(GENERATOR_SPECS)
    return {"xc_source": g(rng), "feature_tags": tags, "difficulty_level": level}


def generate_one(rng: random.Random) -> str:
    return generate_one_with_meta(rng)["xc_source"]


def hierarchical_wrap(xc_source: str) -> tuple[str, dict]:
    raw_lines = xc_source.splitlines()
    lines = [ln for ln in raw_lines if ln.strip()]
    out: List[str] = ["<<<PROGRAM>>>"]
    spans: List[Dict] = []
    for i, line in enumerate(lines):
        out.append(f"<<<STMT_{i}>>>{line}")
        spans.append({"i": i, "text": line.strip()[:220]})
    return "\n".join(out), {"statements": spans, "tokens_hint": "per_stmt"}
