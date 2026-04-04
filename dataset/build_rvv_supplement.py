#!/usr/bin/env python3
"""生成 dataset/xc_asm_rvv_supplement.jsonl（RVV 金汇编 + 标量寄存器/流水注释题）。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _hier(xc: str) -> str:
    lines = [ln for ln in xc.splitlines() if ln.strip()]
    return "<<<PROGRAM>>>\n" + "\n".join(f"<<<STMT_{i}>>>{ln}" for i, ln in enumerate(lines))


def _row(
    rid: str,
    xc: str,
    asm: str,
    tags: list,
    diff: str,
    *,
    rvv_asm: bool,
) -> dict:
    return {
        "id": rid,
        "xc_source": xc,
        "asm_riscv64": asm.strip(),
        "c_reference": "",
        "hierarchical_input": _hier(xc),
        "spans": {"statements": []},
        "feature_tags": tags,
        "difficulty_level": diff,
        "unsupported_reason": None,
        "meta": {
            "isa": "riscv64",
            "dialect": "gnu",
            "seed": 880000,
            "rvv_assembly": rvv_asm,
            "qemu_requires": "qemu-user-8.x-rvv" if rvv_asm else "any",
        },
        "xc_hash": rid,
    }


ASM_SUM_1234 = r""".file	"xc_oracle.s"
	.data
	.align	4
arr:
	.word	1, 2, 3, 4
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -16
	sd	ra, 8(sp)
	la	t0, arr
	li	t1, 4
	vsetvli	t2, t1, e32, m1, ta, ma
	vle32.v	v0, (t0)
	vmv.v.i	v1, 0
	vredsum.vs	v0, v0, v1
	vmv.x.s	a0, v0
	ld	ra, 8(sp)
	addi	sp, sp, 16
	ret
	.size	main, .-main"""

ASM_VZERO = r""".file	"xc_oracle.s"
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -16
	sd	ra, 8(sp)
	li	t1, 4
	vsetvli	t0, t1, e32, m1, ta, ma
	vmv.v.i	v0, 0
	li	a0, 0
	ld	ra, 8(sp)
	addi	sp, sp, 16
	ret
	.size	main, .-main"""

ASM_VLE_CONST = r""".file	"xc_oracle.s"
	.data
	.align	4
w:
	.word	42
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -16
	sd	ra, 8(sp)
	la	t0, w
	li	t1, 1
	vsetvli	t2, t1, e32, m1, ta, ma
	vle32.v	v0, (t0)
	vmv.x.s	a0, v0
	ld	ra, 8(sp)
	addi	sp, sp, 16
	ret
	.size	main, .-main"""

ASM_VADD_PAIR = r""".file	"xc_oracle.s"
	.data
	.align	4
va:
	.word	10, 20
vb:
	.word	3, 4
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -16
	sd	ra, 8(sp)
	la	t0, va
	la	t1, vb
	li	t2, 2
	vsetvli	t3, t2, e32, m1, ta, ma
	vle32.v	v0, (t0)
	vle32.v	v1, (t1)
	vadd.vv	v2, v0, v1
	vmv.x.s	a0, v2
	ld	ra, 8(sp)
	addi	sp, sp, 16
	ret
	.size	main, .-main"""

ASM_VSPLAT7 = r""".file	"xc_oracle.s"
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -16
	sd	ra, 8(sp)
	li	t1, 4
	vsetvli	t0, t1, e32, m1, ta, ma
	vmv.v.i	v0, 7
	vmv.x.s	a0, v0
	ld	ra, 8(sp)
	addi	sp, sp, 16
	ret
	.size	main, .-main"""

ASM_SCALAR_ADD23 = r""".file	"xc_oracle.s"
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -160
	sd	ra, 152(sp)
	sd	s0, 144(sp)
	mv	s0, sp
	li	a0, 2
	sw	a0, 0(s0)
	li	a0, 3
	sw	a0, 8(s0)
	lw	a0, 0(s0)
	addi	sp, sp, -16
	sd	a0, 8(sp)
	lw	a0, 8(s0)
	ld	t0, 8(sp)
	addi	sp, sp, 16
	addw	a0, t0, a0
	j	.L_exit_main
	li	a0, 0
.L_exit_main:
	mv	sp, s0
	ld	s0, 144(sp)
	ld	ra, 152(sp)
	addi	sp, sp, 160
	ret
	.size	main, .-main"""

ASM_SCALAR_ADD3 = r""".file	"xc_oracle.s"
	.text
	.globl	main
	.type	main, @function
main:
	addi	sp, sp, -176
	sd	ra, 168(sp)
	sd	s0, 160(sp)
	mv	s0, sp
	li	a0, 5
	sw	a0, 0(s0)
	li	a0, 6
	sw	a0, 8(s0)
	li	a0, 7
	sw	a0, 16(s0)
	lw	a0, 0(s0)
	addi	sp, sp, -16
	sd	a0, 8(sp)
	lw	a0, 8(s0)
	ld	t0, 8(sp)
	addi	sp, sp, 16
	addw	a0, t0, a0
	addi	sp, sp, -16
	sd	a0, 8(sp)
	lw	a0, 16(s0)
	ld	t0, 8(sp)
	addi	sp, sp, 16
	addw	a0, t0, a0
	j	.L_exit_main
	li	a0, 0
.L_exit_main:
	mv	sp, s0
	ld	s0, 160(sp)
	ld	ra, 168(sp)
	addi	sp, sp, 176
	ret
	.size	main, .-main"""


def main() -> None:
    rows = [
        _row(
            "rvv_sup_sum10",
            "# [RVV] 使用向量指令：.data 中 4 个 int32 为 1,2,3,4，求和作为 main 返回值。\n# {\n    ^ 0\n# }\n",
            ASM_SUM_1234,
            ["rvv", "reduce"],
            "medium",
            rvv_asm=True,
        ),
        _row(
            "rvv_sup_zero",
            "# [RVV] vsetvli(e32,m1,ta,ma) 后量寄存器清零，main 返回 0。\n# {\n    ^ 0\n# }\n",
            ASM_VZERO,
            ["rvv"],
            "easy",
            rvv_asm=True,
        ),
        _row(
            "rvv_sup_load42",
            "# [RVV] 从 .data 加载单个 int32（42），用 vle32.v 放入 a0 返回。\n# {\n    ^ 0\n# }\n",
            ASM_VLE_CONST,
            ["rvv", "load"],
            "easy",
            rvv_asm=True,
        ),
        _row(
            "regalloc_sup_chain",
            "# [寄存器分配] Oracle 风格三变量相加 5+6+7；复用 t0 与栈临时槽。\n# {\n    $x: int = 5\n    $y: int = 6\n    $z: int = 7\n    ^ x + y + z\n# }\n",
            ASM_SCALAR_ADD3,
            ["arith", "multi_slot", "regalloc_hint"],
            "easy",
            rvv_asm=False,
        ),
        _row(
            "rvv_sup_vadd_pair",
            "# [RVV] 两个长度 2 的 int32 数组对应元素相加，返回第一对和（10+3=13）。\n# {\n    ^ 0\n# }\n",
            ASM_VADD_PAIR,
            ["rvv", "arith"],
            "medium",
            rvv_asm=True,
        ),
        _row(
            "rvv_sup_splat7",
            "# [RVV] vsetvli 后 vmv.v.i 将向量置常数 7，取 lane0 经 a0 返回。\n# {\n    ^ 0\n# }\n",
            ASM_VSPLAT7,
            ["rvv"],
            "easy",
            rvv_asm=True,
        ),
        _row(
            "regalloc_sup_add23",
            "# [寄存器分配] 两局部 int 相加 2+3；Oracle 帧与 addw。\n# {\n    $x: int = 2\n    $y: int = 3\n    ^ x + y\n# }\n",
            ASM_SCALAR_ADD23,
            ["arith", "regalloc_hint"],
            "easy",
            rvv_asm=False,
        ),
    ]
    out = ROOT / "xc_asm_rvv_supplement.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
