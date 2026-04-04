#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬规则校验：RISC-V GNU 汇编语法（调用外部 as）与可选执行对拍。
无工具链时仅返回 skipped，不阻断流水线。
"""

from __future__ import annotations

import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import os
import shutil
import sys

# 与 xc_asm_config.py 保持一致的 ISA / 工具探测（内联避免路径编码问题）
ISA_NAME = "riscv64"
ASM_DIALECT = "gnu"
ENV_AS = "XC_RISCV_AS"
ENV_LD = "XC_RISCV_LD"
ENV_GCC = "XC_RISCV_GCC"
ENV_QEMU = "XC_RISCV_QEMU"
DEFAULT_AS_CMDS = ("riscv64-linux-gnu-as", "riscv64-unknown-linux-gnu-as", "as")
DEFAULT_LD_CMDS = ("riscv64-linux-gnu-ld", "riscv64-unknown-linux-gnu-ld", "ld")
DEFAULT_GCC_CMDS = ("riscv64-linux-gnu-gcc", "riscv64-unknown-linux-gnu-gcc")
DEFAULT_QEMU_CMDS = ("qemu-riscv64",)

_RVV_ASM_HINT = re.compile(
    r"\b(vsetvli|vsetivli|vl[re]\d+\.v|vse\d+\.v|v[fs]?(?:add|sub|mul|div|macc)[^,\s]*|"
    r"vmv\.[^,\s]+|vredsum|vcompress|vslide|vfclass|vfsqrt)\b"
)


def asm_uses_rvv(asm: str) -> bool:
    return bool(_RVV_ASM_HINT.search(asm))


def _riscv_march_token(asm: str) -> str:
    override = os.environ.get("XC_RISCV_MARCH", "").strip()
    if override:
        return override
    return "rv64gcv" if asm_uses_rvv(asm) else "rv64gc"


def riscv_march_gcc_args(asm: str) -> list:
    return [f"-march={_riscv_march_token(asm)}", "-mabi=lp64d"]


def riscv_march_as_args(asm: str) -> list:
    return [f"-march={_riscv_march_token(asm)}", "-mabi=lp64d"]


def qemu_riscv_extra_args(asm: str) -> list:
    """用户态 QEMU 默认 CPU 常无 V；RVV ELF 需显式 -cpu。"""
    cpu = os.environ.get("XC_RISCV_QEMU_CPU", "").strip()
    if cpu:
        return ["-cpu", cpu]
    if asm_uses_rvv(asm):
        return ["-cpu", "rv64,v=true,vlen=128,vext_spec=v1.0"]
    return []


def resolve_tool(cmds: tuple, env_key: str):
    override = os.environ.get(env_key, "").strip()
    if override:
        return override
    for c in cmds:
        p = shutil.which(c)
        if p:
            return p
    return None


def get_toolchain_info() -> dict:
    return {
        "isa": ISA_NAME,
        "dialect": ASM_DIALECT,
        "as": resolve_tool(DEFAULT_AS_CMDS, ENV_AS),
        "ld": resolve_tool(DEFAULT_LD_CMDS, ENV_LD),
        "gcc": resolve_tool(DEFAULT_GCC_CMDS, ENV_GCC),
        "qemu": resolve_tool(DEFAULT_QEMU_CMDS, ENV_QEMU),
    }


_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def basic_asm_sanity(asm: str) -> Tuple[bool, str]:
    """轻量启发式：标签、指令助记符粗检（无外部工具时兜底）。"""
    if not asm.strip():
        return False, "empty"
    if "__XC_DPO_REJECT__" in asm:
        return False, "synthetic_reject_marker"
    if ".text" not in asm and ".globl" not in asm:
        return False, "missing text/globl"
    hints = ("addi", "lw", "sw", "addw", "ret", "call", "j\t", "beqz", "vsetvli", "vle")
    if not any(h in asm for h in hints):
        return False, "no recognizable rv64 hints"
    return True, "ok"


def assemble_check(asm: str, extra_flags: Optional[list] = None) -> Tuple[bool, str]:
    """调用 riscv64-*-as 做语法检查。"""
    info = get_toolchain_info()
    as_path = info.get("as")
    if not as_path:
        ok, msg = basic_asm_sanity(asm)
        return ok, f"no_as_tool:{msg}"

    extra_flags = extra_flags or []
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.s"
        p.write_text(asm, encoding="utf-8")
        out_o = Path(td) / "t.o"
        march = riscv_march_as_args(asm)
        cmd = [as_path, *march, *extra_flags, "-o", str(out_o), str(p)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return False, str(e)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()[:2000]
            return False, err or "as failed"
        if not out_o.is_file():
            return False, "no object file"
        return True, "assembled"


def mutate_xc_source_light(xc: str, rng: random.Random) -> str:
    """
    对 XC 做轻量合法扰动（用于 fuzz / 对抗池）：改一个整数字面量 ±1，或插入空行。
    不改变结构块括号。
    """
    lines = xc.splitlines()
    if not lines:
        return xc
    idxs = [i for i, ln in enumerate(lines) if any(c.isdigit() for c in ln) and "$" in ln]
    if idxs and rng.random() < 0.85:
        i = rng.choice(idxs)
        ln = lines[i]
        out = []
        changed = False
        for ch in ln:
            if ch.isdigit() and not changed:
                d = int(ch)
                nd = (d + rng.choice([-1, 1])) % 10
                out.append(str(nd))
                changed = True
            else:
                out.append(ch)
        lines[i] = "".join(out)
    else:
        insert_at = rng.randint(0, len(lines))
        lines.insert(insert_at, "    // fuzz")
    return "\n".join(lines) + ("\n" if xc.endswith("\n") else "")


def corrupt_asm_negative_sample(asm: str) -> str:
    """构造 rejected 侧样本；含 __XC_DPO_REJECT__ 使 basic_asm_sanity 失败。"""
    lines = asm.splitlines()
    if not lines:
        return asm + "\n__XC_DPO_REJECT__\n"
    for i, ln in enumerate(lines):
        if "\tcall\t" in ln:
            lines[i] = ln.replace("call", "call_broken")
            break
        if "\taddi\tsp" in ln and i > 0:
            lines[i] = "\taddi\tsp, sp, 999999999"
            break
    else:
        lines.append("\t.word\t0")
    lines.append("/* __XC_DPO_REJECT__ */")
    return "\n".join(lines) + "\n"


def rule_reward_score(asm: str) -> dict:
    """规则奖励分量（RLHF / 过滤）。"""
    ok_as, as_msg = assemble_check(asm)
    ok_s, s_msg = basic_asm_sanity(asm)
    n_lines = len([x for x in asm.splitlines() if x.strip() and not x.strip().startswith("#")])
    brevity = max(0, 1.0 - min(n_lines, 500) / 500.0)
    return {
        "assemble_ok": ok_as,
        "assemble_msg": as_msg[:500],
        "sanity_ok": ok_s,
        "sanity_msg": s_msg,
        "lines": n_lines,
        "brevity_bonus": round(brevity, 4),
        "reward": (1.0 if ok_as else 0.0) + (0.1 * brevity if ok_as else 0.0),
    }


def try_qemu_run_elf(elf_path: Path, timeout: float = 3.0) -> Tuple[Optional[int], str]:
    info = get_toolchain_info()
    qemu = info.get("qemu")
    if not qemu:
        return None, "no_qemu"
    try:
        r = subprocess.run([qemu, str(elf_path)], capture_output=True, timeout=timeout)
        return r.returncode, "ok"
    except Exception as e:
        return None, str(e)


def try_compile_and_qemu_exit_code(asm: str) -> Tuple[Optional[int], str]:
    """Host riscv64 gcc + qemu-riscv64：全静态链接常规 Linux 启动文件，使 .globl main 可正常进入。"""
    import shutil

    gcc = shutil.which("riscv64-linux-gnu-gcc") or shutil.which("riscv64-unknown-linux-gnu-gcc")
    qemu = shutil.which("qemu-riscv64")
    if not gcc:
        return None, "no_riscv_gcc"
    if not qemu:
        return None, "no_qemu"
    with tempfile.TemporaryDirectory() as td:
        s_path = Path(td) / "t.s"
        elf = Path(td) / "t"
        s_path.write_text(asm, encoding="utf-8")
        r = subprocess.run(
            # Do not use -nostdlib: Oracle 输出为带 main 的 GNU 汇编，需要 crt 把控制流交到 main。
            [gcc, "-static", *riscv_march_gcc_args(asm), str(s_path), "-o", str(elf)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0 or not elf.is_file():
            return None, (r.stderr or r.stdout or "link_failed")[:800]
        try:
            rq = subprocess.run([qemu, *qemu_riscv_extra_args(asm), str(elf)], capture_output=True, timeout=5)
            return rq.returncode, "ran"
        except Exception as e:
            return None, str(e)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("asm_file", type=str, nargs="?", help="path to .s file")
    args = ap.parse_args()
    if args.asm_file:
        t = Path(args.asm_file).read_text(encoding="utf-8")
        print(assemble_check(t))
        print(rule_reward_score(t))
    else:
        print(get_toolchain_info())
