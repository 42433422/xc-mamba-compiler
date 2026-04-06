#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成复杂控制流 / 大规模 XC / 工业风格场景的 Oracle 金标 JSONL。

说明（与当前 xc_asm_oracle 能力对齐）：
- 递归、多函数、深层 if/while/for、break/continue：支持。
- 真数组下标 arr[i]、*p 解引用：Oracle 尚未支持；「高维」用扁平槽位 + 行主序索引公式
  （如 idx = row * W + col）与分支累加模拟，便于训练寄存器/控制流而非 C 级 lowering。
- 指针：保留 *int + ΩM(malloc) 等已有子集；复杂负载通过「缓冲区长度 + 校验和链」表达。

输出：dataset/xc_asm_complex_supplement.jsonl
合并进训练集示例见 dataset/evaluation_spec.json。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dataset.build_xc_asm_corpus import build_record, xc_hash
from dataset.xc_asm_synth import hierarchical_wrap


def _norm(s: str) -> str:
    return "\n".join(x.rstrip() for x in s.strip().splitlines())


def gen_long_arith_chain(lines_body: int = 112) -> str:
    """单累加器反复线性混合，行数可控（默认 >100 行 XC）。"""
    parts: List[str] = ["# {", "    $acc: int = 11"]
    for i in range(1, lines_body):
        k = (i * 17 + 3) % 31
        m = (i * 5 + 1) % 7
        parts.append(f"    $acc: int = acc * {k % 5 + 2} + {k} - {m}")
    parts.extend(["    ^ acc", "}"])
    return "\n".join(parts)


def gen_flat_grid_row_major_sum(rows: int, cols: int) -> str:
    """用命名槽位模拟 rows*cols 矩阵，按行主序累加（无 []）。"""
    n = rows * cols
    vals = [(i * 13 + (i // cols) * 3 + (i % cols) * 5) % 97 for i in range(n)]
    lines: List[str] = ["# {", f"    $rows: int = {rows}", f"    $cols: int = {cols}", "    $sum: int = 0"]
    for i, v in enumerate(vals):
        lines.append(f"    $c{i}: int = {v}")
    for i in range(n):
        lines.append(f"    $sum: int = sum + c{i}")
    lines.extend(["    ^ sum", "}"])
    return "\n".join(lines)


def gen_crc_style_pipeline(steps: int = 48) -> str:
    """工业风格：多步 XOR/移位链（无 `%`/无按位与赋值，规避 XC 词法限制）。"""
    imm_pool = (32, 144, 200, 100, 50, 17, 9, 4, 221, 19, 88, 3, 201, 44, 12, 99)
    lines: List[str] = ["# {", "    $crc: int = 305419896"]
    for s in range(steps):
        imm = imm_pool[s - (s // 16) * 16]
        lines.append(f"    $crc: int = crc ^ {imm}")
        lines.append("    $crc: int = crc + (crc << 1)")
        lines.append("    $crc: int = crc ^ (crc >> 3)")
    lines.extend(["    ^ crc", "}"])
    return "\n".join(lines)


def gen_state_machine_router() -> str:
    """简化协议/解析状态机：多状态、多条件路由。"""
    return """# {
    $state: int = 0
    $byte0: int = 170
    $byte1: int = 187
    $byte2: int = 204
    $err: int = 0
    ? (state == 0) {
        ? (byte0 == 170) {
            $state: int = 1
        } ?: {
            $err: int = 1
        }
    }
    ? (state == 1) {
        ? (byte1 == 187) {
            $state: int = 2
        } ?: {
            $err: int = 2
        }
    }
    ? (state == 2) {
        ? (byte2 == 204) {
            $state: int = 3
        } ?: {
            $err: int = 3
        }
    }
    ? (state == 3) {
        $err: int = 0
    }
    ^ state * 1000 + err
}"""


SPECS: List[Dict[str, Any]] = [
    {
        "id": "xcasm_complex_fib_8",
        "xc_source": """# {
    % fib(n: int) -> int {
        ? (n <= 1) {
            ^ n
        } ?: {
            ^ fib(n - 1) + fib(n - 2)
        }
    }
    ^ fib(8)
}""",
        "feature_tags": ["recursion", "multi_func", "arith"],
        "difficulty_level": "hard",
        "scenario": "递归 Fibonacci（深度控制流 + 调用栈）",
    },
    {
        "id": "xcasm_complex_fact_6",
        "xc_source": """# {
    % fact(n: int) -> int {
        ? (n <= 1) {
            ^ 1
        } ?: {
            ^ n * fact(n - 1)
        }
    }
    ^ fact(6)
}""",
        "feature_tags": ["recursion", "multi_func"],
        "difficulty_level": "hard",
        "scenario": "递归阶乘",
    },
    {
        "id": "xcasm_complex_gcd_iter",
        "xc_source": """# {
    % gcd(a: int, b: int) -> int {
        while ((a != b)) {
            ? (a > b) {
                $a: int = a - b
            } ?: {
                $b: int = b - a
            }
        }
        ^ a
    }
    ^ gcd(84, 30)
}""",
        "feature_tags": ["while", "multi_func", "industrial_algo", "sub_gcd"],
        "difficulty_level": "hard",
        "scenario": "二进制减法版 GCD（避免 XC 中 % 与函数符冲突）",
    },
    {
        "id": "xcasm_complex_even_odd",
        "xc_source": """# {
    % is_even(n: int) -> int {
        ? (n == 0) {
            ^ 1
        } ?: {
            ^ is_odd(n - 1)
        }
    }
    % is_odd(n: int) -> int {
        ? (n == 0) {
            ^ 0
        } ?: {
            ^ is_even(n - 1)
        }
    }
    ^ is_even(10)
}""",
        "feature_tags": ["recursion", "mutual_recursion", "multi_func"],
        "difficulty_level": "hard",
        "scenario": "互递归奇偶判定",
    },
    {
        "id": "xcasm_complex_nested_break",
        "xc_source": """# {
    $out: int = 0
    ~i: int = 0; i < 20; i++ {
        ? (i == 7) {
            >
        }
        ? ((i - (i / 3) * 3) == 0) {
            $out: int = out + i
        }
    }
    ^ out
}""",
        "feature_tags": ["for", "break", "arith", "div_mod_equiv"],
        "difficulty_level": "medium",
        "scenario": "for + break + 整除等价于 mod 3 的累加",
    },
    {
        "id": "xcasm_complex_malloc_chain",
        "xc_source": """# {
    $n: int = 5
    $p: *int = ΩM(4 * n)
    $q: *int = ΩM(4 * 8)
    $a: int = n + 8
    ^ a
}""",
        "feature_tags": ["pointer", "malloc", "multi_slot"],
        "difficulty_level": "hard",
        "scenario": "双缓冲区分配（嵌入式堆管理意图）",
    },
    {
        "id": "xcasm_complex_deep_if",
        "xc_source": """# {
    $x: int = 42
    $r: int = 0
    ? (x < 10) {
        $r: int = 1
    } ?? (x < 30) {
        $r: int = 2
    } ?? (x < 50) {
        $r: int = 3
    } ?: {
        $r: int = 4
    }
    ^ r
}""",
        "feature_tags": ["if", "elif", "compare"],
        "difficulty_level": "medium",
        "scenario": "多分支 elif 链",
    },
    {
        "id": "xcasm_complex_fsm",
        "xc_source": None,
        "generator": gen_state_machine_router,
        "feature_tags": ["industrial_fsm", "if", "multi_slot"],
        "difficulty_level": "hard",
        "scenario": "工业风格包头解析状态机",
    },
    {
        "id": "xcasm_complex_grid_4x4",
        "xc_source": None,
        "generator": lambda: gen_flat_grid_row_major_sum(4, 4),
        "feature_tags": ["pseudo_2d", "flat_index", "multi_slot", "arith"],
        "difficulty_level": "hard",
        "scenario": "4x4 矩阵槽位模拟 + 全量求和",
    },
    {
        "id": "xcasm_complex_long_chain",
        "xc_source": None,
        "generator": lambda: gen_long_arith_chain(115),
        "feature_tags": ["large_code", "long_chain", "arith"],
        "difficulty_level": "hard",
        "scenario": "115+ 行线性算术链（大规模单函数体）",
    },
    {
        "id": "xcasm_complex_crc_pipe",
        "xc_source": None,
        "generator": lambda: gen_crc_style_pipeline(40),
        "feature_tags": ["industrial_crc", "bitwise_chain", "large_code"],
        "difficulty_level": "hard",
        "scenario": "类 CRC 多步混合（管道式数据处理）",
    },
]


def _materialize(spec: Dict[str, Any]) -> Dict[str, Any]:
    xc = spec.get("xc_source")
    if xc is None and "generator" in spec:
        xc = spec["generator"]()
    assert xc
    return {
        "id": spec["id"],
        "xc_source": _norm(xc),
        "feature_tags": spec["feature_tags"],
        "difficulty_level": spec["difficulty_level"],
        "scenario": spec.get("scenario", ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="构建复杂场景 XC↔ASM 补充集")
    ap.add_argument("--out", type=str, default=str(ROOT / "dataset" / "xc_asm_complex_supplement.jsonl"))
    ap.add_argument("--seed", type=int, default=770077)
    args = ap.parse_args()
    out_path = Path(args.out)

    rows: List[Dict[str, Any]] = []
    for i, spec in enumerate(SPECS):
        item = _materialize(spec)
        rec = build_record(
            {"xc_source": item["xc_source"], "feature_tags": item["feature_tags"], "difficulty_level": item["difficulty_level"]},
            args.seed,
            i,
            keep_unsupported=False,
        )
        if rec is None:
            print(f"[skip] oracle unsupported: {item['id']}", file=sys.stderr)
            continue
        rec["id"] = item["id"]
        rec["xc_hash"] = xc_hash(item["xc_source"])
        hier, span_meta = hierarchical_wrap(item["xc_source"])
        rec["hierarchical_input"] = hier
        rec["spans"] = span_meta
        if item.get("scenario"):
            rec.setdefault("meta", {})
            if isinstance(rec["meta"], dict):
                rec["meta"]["scenario_note"] = item["scenario"]
                rec["meta"]["corpus_tier"] = "complex_industrial"
        rows.append(rec)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as wf:
        for r in rows:
            wf.write(json.dumps(r, ensure_ascii=False) + "\n")

    nlines = [len(r["xc_source"].splitlines()) for r in rows]
    print(f"wrote {len(rows)} rows -> {out_path}")
    print(f"xc_source line counts: min={min(nlines)} max={max(nlines)}")


if __name__ == "__main__":
    main()
