"""RVV 相关脚手架：寄存器池、调度器与示例片段生成。

未接入主编译流水线；其中的性能/精度数字未经实测，勿当作基准。"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum, auto


class VectorRegType(Enum):
    A = auto()
    B = auto()
    C = auto()
    DT = auto()
    X = auto()


@dataclass
class VectorReg:
    name: str
    reg_type: VectorRegType
    lanes: int = 0
    is_dirty: bool = False
    last_use: int = 0
    allocation_time: int = 0
    is_live: bool = True


@dataclass
class VectorRegAllocator:
    regs_a: List[str] = field(default_factory=list)
    regs_b: List[str] = field(default_factory=list)
    regs_c: List[str] = field(default_factory=list)
    regs_dt: List[str] = field(default_factory=list)
    regs_x: List[str] = field(default_factory=list)
    alloc_order: List[Tuple[str, VectorRegType, int]] = field(default_factory=list)
    use_count: Dict[str, int] = field(default_factory=dict)
    next_alloc_id: int = 0

    def __post_init__(self):
        self.regs_a = [f"v{i}" for i in range(8)]
        self.regs_b = [f"v{i}" for i in range(8, 16)]
        self.regs_c = [f"v{i}" for i in range(16, 24)]
        self.regs_dt = [f"v{i}" for i in range(24, 28)]
        self.regs_x = [f"v{i}" for i in range(28, 32)]

    def get_pool(self, reg_type: VectorRegType) -> List[str]:
        if reg_type == VectorRegType.A:
            return self.regs_a
        elif reg_type == VectorRegType.B:
            return self.regs_b
        elif reg_type == VectorRegType.C:
            return self.regs_c
        elif reg_type == VectorRegType.DT:
            return self.regs_dt
        return self.regs_x

    def allocate(self, reg_type: VectorRegType, hint_reg: Optional[str] = None) -> str:
        pool = self.get_pool(reg_type)
        if hint_reg and hint_reg in pool:
            return hint_reg
        alloc_id = self.next_alloc_id
        self.next_alloc_id += 1
        reg = pool[alloc_id % len(pool)]
        self.alloc_order.append((reg, reg_type, alloc_id))
        self.use_count[reg] = self.use_count.get(reg, 0) + 1
        return reg

    def allocate_multi(self, count: int, reg_type: VectorRegType) -> List[str]:
        return [self.allocate(reg_type) for _ in range(count)]

    def deallocate(self, reg: str):
        if reg in self.use_count:
            self.use_count[reg] -= 1
            if self.use_count[reg] <= 0:
                del self.use_count[reg]

    def get_stats(self) -> Dict[str, int]:
        return {
            "total_regs": 32,
            "used_regs": len(self.use_count),
            "alloc_count": self.next_alloc_id,
        }


@dataclass
class VectorRegState:
    regs: Dict[str, VectorReg] = field(default_factory=dict)
    alloc_counter: int = 0
    next_use_counter: int = 0
    allocator: VectorRegAllocator = field(default_factory=VectorRegAllocator)

    def alloc(self, reg_type: VectorRegType, lanes: int = 8) -> VectorReg:
        self.alloc_counter += 1
        reg_name = self.allocator.allocate(reg_type)
        reg = VectorReg(
            name=reg_name,
            reg_type=reg_type,
            lanes=lanes,
            is_dirty=False,
            last_use=self.next_use_counter,
            allocation_time=self.alloc_counter
        )
        self.regs[reg_name] = reg
        return reg

    def alloc_vector_group(self, count: int, reg_type: VectorRegType, lanes: int = 8) -> List[VectorReg]:
        reg_names = self.allocator.allocate_multi(count, reg_type)
        result = []
        for name in reg_names:
            self.alloc_counter += 1
            reg = VectorReg(
                name=name,
                reg_type=reg_type,
                lanes=lanes,
                is_dirty=False,
                last_use=self.next_use_counter,
                allocation_time=self.alloc_counter
            )
            self.regs[name] = reg
            result.append(reg)
        return result

    def get_free_reg(self, preferred_type: Optional[VectorRegType] = None) -> VectorReg:
        for reg in self.regs.values():
            if not reg.is_dirty and reg.reg_type == preferred_type:
                return reg
        return self.alloc(preferred_type or VectorRegType.X)

    def get_least_recently_used(self, reg_type: Optional[VectorRegType] = None) -> Optional[VectorReg]:
        candidates = [r for r in self.regs.values() if not r.is_dirty and (reg_type is None or r.reg_type == reg_type)]
        if not candidates:
            return None
        return min(candidates, key=lambda r: r.last_use)

    def mark_dirty(self, reg_name: str):
        if reg_name in self.regs:
            self.regs[reg_name].is_dirty = True
            self.regs[reg_name].last_use = self.next_use_counter
        self.next_use_counter += 1

    def mark_clean(self, reg_name: str):
        if reg_name in self.regs:
            self.regs[reg_name].is_dirty = False

    def mark_use(self, reg_name: str):
        if reg_name in self.regs:
            self.regs[reg_name].last_use = self.next_use_counter
        self.next_use_counter += 1

    def get_live_regs(self) -> List[str]:
        return [r.name for r in self.regs.values() if r.is_live]

    def reset(self):
        self.regs.clear()
        self.alloc_counter = 0
        self.next_use_counter = 0
        self.allocator = VectorRegAllocator()


class PipelineStage:
    def __init__(self, name: str, latency: int = 1):
        self.name = name
        self.latency = latency
        self.issued_at: Optional[int] = None
        self.completed_at: Optional[int] = None

    def issue(self, cycle: int):
        self.issued_at = cycle

    def complete(self, cycle: int):
        self.completed_at = cycle

    def stall_cycles(self, other: "PipelineStage") -> int:
        if self.completed_at and other.issued_at:
            if self.completed_at > other.issued_at:
                return self.completed_at - other.issued_at
        return 0


class SoftwarePipeline:
    def __init__(self, ii: int = 1):
        self.ii = ii
        self.stages: List[PipelineStage] = []
        self.cycle: int = 0

    def add_stage(self, name: str, latency: int = 1):
        self.stages.append(PipelineStage(name, latency))

    def schedule(self) -> List[Tuple[int, str]]:
        schedule = []
        self.cycle = 0
        for stage in self.stages:
            stage.issue(self.cycle)
            schedule.append((self.cycle, stage.name))
            self.cycle += stage.latency
        return schedule

    def get_initiation_interval(self) -> int:
        return self.ii

    def compute_throughput(self, iterations: int) -> int:
        if not self.stages:
            return 0
        total_latency = sum(s.latency for s in self.stages)
        return total_latency + (iterations - 1) * self.ii


class LoopUnrollFactor:
    UNROLL_2 = 2
    UNROLL_4 = 4
    UNROLL_8 = 8


@dataclass
class UnrollSchedule:
    factor: int
    loop_carried_deps: List[str] = field(default_factory=list)
    regs_per_iteration: int = 0

    def get_unrolled_iterations(self, original_iters: int) -> int:
        return (original_iters + self.factor - 1) // self.factor


class RVVPipelineScheduler:
    def __init__(self):
        self.pending_loads: List[str] = []
        self.pending_muls: List[str] = []
        self.pending_adds: List[str] = []
        self.pending_stores: List[str] = []
        self.schedule: List[Tuple[int, str, str]] = []
        self.cycle: int = 0
        self.ii_load = 1
        self.ii_mul = 2
        self.ii_add = 1

    def add_load(self, reg: str, address: str):
        self.pending_loads.append(reg)
        self._schedule_stage(self.cycle, "LOAD", reg)

    def add_mul(self, dest: str, src1: str, src2: str):
        self.pending_muls.append(dest)
        self._schedule_stage(self.cycle + 1, "MUL", dest)

    def add_add(self, dest: str, src1: str, src2: str):
        self.pending_adds.append(dest)
        self._schedule_stage(self.cycle + 2, "ADD", dest)

    def add_store(self, reg: str, address: str):
        self.pending_stores.append(reg)
        self._schedule_stage(self.cycle + 3, "STORE", reg)

    def _schedule_stage(self, cycle: int, stage_type: str, reg: str):
        self.schedule.append((cycle, stage_type, reg))

    def advance_cycle(self):
        self.cycle += 1

    def get_schedule(self) -> List[Tuple[int, str, str]]:
        return sorted(self.schedule, key=lambda x: x[0])

    def get_ii(self) -> int:
        return max(self.ii_load, self.ii_mul, self.ii_add)


def create_pipelined_dot_product(a_reg: str, b_reg: str, result_reg: str, n_reg: str) -> List[str]:
    asm = []
    asm.append("    # Software-pipelined dot product with RVV")
    asm.append("    mv t0, a0")
    asm.append("    mv t1, a1")
    asm.append("    mv t2, a2")
    asm.append("    srai t3, a3, 3")
    asm.append("    andi t4, a3, 7")
    asm.append("    li t5, 8")
    asm.append("    # Initialize accumulator registers")
    asm.append("    vmv.v.i v0, zero")
    asm.append("    vmv.v.i v1, zero")
    asm.append("    vmv.v.i v2, zero")
    asm.append("    vmv.v.i v3, zero")
    asm.append("    # Prologue: prime the pipeline")
    asm.append("    blez t3, .Lpipelined_remainder")
    asm.append("    vsetvl t6, t5, 8")
    asm.append("    vle32.v v8, (t0)")
    asm.append("    vle32.v v9, (t1)")
    asm.append("    addi t0, t0, 128")
    asm.append("    addi t1, t1, 128")
    asm.append("    addi t3, t3, -8")
    asm.append("    # Main pipelined loop")
    asm.append(".Lpipelined_main:")
    asm.append("    vsetvl t6, t5, 8")
    asm.append("    vle32.v v16, (t0)")
    asm.append("    vle32.v v17, (t1)")
    asm.append("    vfmul.vv v18, v8, v9")
    asm.append("    vfadd.vv v0, v0, v18")
    asm.append("    addi t0, t0, 128")
    asm.append("    addi t1, t1, 128")
    asm.append("    vle32.v v8, (t0)")
    asm.append("    vle32.v v9, (t1)")
    asm.append("    addi t3, t3, -8")
    asm.append("    bgtz t3, .Lpipelined_main")
    asm.append("    # Epilogue: drain the pipeline")
    asm.append("    vfmul.vv v18, v8, v9")
    asm.append("    vfadd.vv v0, v0, v18")
    asm.append("    # Reduction phase")
    asm.append(".Lpipelined_remainder:")
    asm.append("    blez t4, .Lpipelined_done")
    asm.append(".Lpipelined_rem_loop:")
    asm.append("    addi t4, t4, -1")
    asm.append("    flw fa0, (t0)")
    asm.append("    flw fa1, (t1)")
    asm.append("    fmul.s fa2, fa0, fa1")
    asm.append("    fadd.s fa3, fa3, fa2")
    asm.append("    addi t0, t0, 4")
    asm.append("    addi t1, t1, 4")
    asm.append("    bgtz t4, .Lpipelined_rem_loop")
    asm.append(".Lpipelined_done:")
    asm.append("    fsrw fa3, v0")
    asm.append("    fsw fa3, (t2)")
    return asm


def create_unrolled_vector_op_4x(ptr_reg: str, n_reg: str, result_reg: str) -> List[str]:
    asm = []
    asm.append("    # 4x Unrolled vector operation with software pipelining")
    asm.append("    mv t0, " + ptr_reg)
    asm.append("    srai t1, " + n_reg + ", 2")
    asm.append("    andi t2, " + n_reg + ", 3")
    asm.append("    # Initialize accumulators")
    asm.append("    vmv.v.i v0, zero")
    asm.append("    vmv.v.i v1, zero")
    asm.append("    vmv.v.i v2, zero")
    asm.append("    vmv.v.i v3, zero")
    asm.append("    blez t1, .Lunrolled_remainder")
    asm.append("    # 4x unrolled main loop with software pipeline")
    asm.append(".Lunrolled_main:")
    asm.append("    vsetvl t6, t0, 8")
    asm.append("    # Load 4 vectors in parallel-ish fashion")
    asm.append("    vle32.v v8, (t0)")
    asm.append("    vle32.v v9, 32(t0)")
    asm.append("    vle32.v v10, 64(t0)")
    asm.append("    vle32.v v11, 96(t0)")
    asm.append("    # Multiply all 4 vectors")
    asm.append("    vfmul.vv v12, v8, v8")
    asm.append("    vfmul.vv v13, v9, v9")
    asm.append("    vfmul.vv v14, v10, v10")
    asm.append("    vfmul.vv v15, v11, v11")
    asm.append("    # Add to accumulators")
    asm.append("    vfadd.vv v0, v0, v12")
    asm.append("    vfadd.vv v1, v1, v13")
    asm.append("    vfadd.vv v2, v2, v14")
    asm.append("    vfadd.vv v3, v3, v15")
    asm.append("    addi t0, t0, 128")
    asm.append("    addi t1, t1, -1")
    asm.append("    bgtz t1, .Lunrolled_main")
    asm.append("    # Horizontal reduction of accumulators")
    asm.append("    vfadd.vv v0, v0, v1")
    asm.append("    vfadd.vv v0, v0, v2")
    asm.append("    vfadd.vv v0, v0, v3")
    asm.append("    # Handle remainder")
    asm.append(".Lunrolled_remainder:")
    asm.append("    blez t2, .Lunrolled_done")
    asm.append(".Lunrolled_rem_loop:")
    asm.append("    addi t2, t2, -1")
    asm.append("    flw fa0, (t0)")
    asm.append("    fmul.s fa1, fa0, fa0")
    asm.append("    fadd.s fa2, fa2, fa1")
    asm.append("    addi t0, t0, 4")
    asm.append("    bgtz t2, .Lunrolled_rem_loop")
    asm.append(".Lunrolled_done:")
    asm.append("    vmv.x.s t0, v0")
    asm.append("    addw t0, t0, fa2")
    asm.append("    sw t0, (a0)")
    return asm


class RVVInstruction:
    def __init__(self, mnemonic: str, *operands: str):
        self.mnemonic = mnemonic
        self.operands = list(operands)

    def __str__(self) -> str:
        return f"{self.mnemonic} {', '.join(self.operands)}"


class RVVVectorCodeGen:
    LMUL_SHIFT = 3
    SEW = 32
    NFIELDS = 1

    def __init__(self):
        self.reg_state = VectorRegState()
        self.instructions: List[RVVInstruction] = []
        self._vl: Optional[str] = None
        self._vtype: Optional[str] = None

    def emit(self, mnemonic: str, *operands: str):
        self.instructions.append(RVVInstruction(mnemonic, *operands))

    def setup_vector_engineering(self, total_elements: int):
        self.emit("csrr", "t0", "vlenb")
        self.emit("slli", "t0", "t0", "2")
        self.emit("mv", "t1", "zero")
        self.emit("bgtz", "t1", ".Lvec_loop")

    def vle32_v(self, dest_reg: str, base_reg: str, offset: str = "0") -> str:
        self.emit("vle32.v", dest_reg, f"{offset}({base_reg})")
        self.reg_state.mark_dirty(dest_reg)
        return dest_reg

    def vse32_v(self, src_reg: str, base_reg: str, offset: str = "0"):
        self.emit("vse32.v", src_reg, f"{offset}({base_reg})")
        self.reg_state.mark_clean(src_reg)

    def vfmul_vv(self, dest_reg: str, src1_reg: str, src2_reg: str) -> str:
        self.emit("vfmul.vv", dest_reg, src1_reg, src2_reg)
        self.reg_state.mark_dirty(dest_reg)
        return dest_reg

    def vfadd_vv(self, dest_reg: str, src1_reg: str, src2_reg: str) -> str:
        self.emit("vfadd.vv", dest_reg, src1_reg, src2_reg)
        self.reg_state.mark_dirty(dest_reg)
        return dest_reg

    def vfmacc_vv(self, dest_reg: str, src1_reg: str, src2_reg: str) -> str:
        self.emit("vfmacc.vv", dest_reg, src1_reg, src2_reg)
        self.reg_state.mark_dirty(dest_reg)
        return dest_reg

    def vid_v(self, dest_reg: str) -> str:
        self.emit("vid.v", dest_reg)
        self.reg_state.mark_dirty(dest_reg)
        return dest_reg

    def vsetvl(self, dest_reg: str, src_reg: str, imm: str) -> str:
        self.emit("vsetvl", dest_reg, src_reg, imm)
        return dest_reg

    def generate_dot_product(self, a_ptr: str, b_ptr: str, result_ptr: str, n: str) -> List[RVVInstruction]:
        ops = []
        result_reg = self.reg_state.alloc(VectorRegType.DT, lanes=1)
        self.emit("# Vecdorized dot product with RVV")
        self.emit("mv", "t0", "a0")
        self.emit("mv", "t1", "a1")
        self.emit("mv", "t2", "a2")
        self.emit("srai", "t3", "a3", "2")
        self.emit("rem", "t4", "t3", "8")
        self.emit("sub", "t3", "t3", "t4")
        self.emit("vmv", "v0", "zero")
        self.emit("vmv", "v1", "zero")
        self.emit("vmv", "v2", "zero")
        self.emit("vmv", "v3", "zero")
        self.emit("vmv", "v4", "zero")
        self.emit("vmv", "v5", "zero")
        self.emit("vmv", "v6", "zero")
        self.emit("vmv", "v7", "zero")
        self.emit("li", "t5", "8")
        self.emit("bgtz", "t3", ".Lvec_main_{i}")
        self.emit("j", ".Lvec_remainder_{i}")
        self.emit(".Lvec_main_{i}:")
        self.emit("vsetvl", "t6", "t5", "8")
        self.emit("vle32.v", "v8", "(t0)")
        self.emit("vle32.v", "v9", "(t1)")
        self.emit("vfmul.vv", "v10", "v8", "v9")
        self.emit("vfadd.vv", "v0", "v0", "v10")
        self.emit("addi", "t0", "t0", "32")
        self.emit("addi", "t1", "t1", "32")
        self.emit("addi", "t3", "t3", "-8")
        self.emit("bgtz", "t3", ".Lvec_main_{i}")
        self.emit(".Lvec_remainder_{i}:")
        self.emit("bltz", "t4", ".Lvec_done_{i}")
        self.emit(".Lvec_rem_loop_{i}:")
        self.emit("addi", "t4", "t4", "-1")
        self.emit("lui", "t6", "%hi(.Lfloat_table_{i})")
        self.emit("addi", "t6", "t6", "%lo(.Lfloat_table_{i})")
        self.emit("slli", "t7", "t4", "2")
        self.emit("add", "t6", "t6", "t7")
        self.emit("flw", "fa0", "(t0)")
        self.emit("flw", "fa1", "(t1)")
        self.emit("fmul.s", "fa2", "fa0", "fa1")
        self.emit("fadd.s", "fa3", "fa3", "fa2")
        self.emit("addi", "t0", "t0", "4")
        self.emit("addi", "t1", "t1", "4")
        self.emit("bgtz", "t4", ".Lvec_rem_loop_{i}")
        self.emit(".Lvec_done_{i}:")
        self.emit("fsw", "v0", "(t2)")
        return self.instructions

    def generate_matrix_multiply(self, A_ptr: str, B_ptr: str, C_ptr: str, M: str, N: str, K: str) -> List[RVVInstruction]:
        self.emit("# Matrix multiplication with RVV")
        self.emit("mv", "t0", A_ptr)
        self.emit("mv", "t1", B_ptr)
        self.emit("mv", "t2", C_ptr)
        self.emit("li", "t3", "8")
        self.emit("outer_loop:")
        self.emit("mv", "t4", "t1")
        self.emit("li", "t5", "8")
        self.emit("inner_loop:")
        self.emit("vsetvl", "t6", "t3", "8")
        self.emit("vle32.v", "v0", "(t0)")
        self.emit("vle32.v", "v1", "(t4)")
        self.emit("vfmul.vv", "v2", "v0", "v1")
        self.emit("vfadd.vv", "v3", "v3", "v2")
        self.emit("vse32.v", "v3", "(t2)")
        self.emit("addi", "t4", "t4", "32")
        self.emit("addi", "t5", "t5", "-1")
        self.emit("bgtz", "t5", "inner_loop")
        self.emit("addi", "t0", "t0", "32")
        self.emit("addi", "t2", "t2", "32")
        self.emit("addi", "t3", "t3", "-1")
        self.emit("bgtz", "t3", "outer_loop")
        return self.instructions

    def generate_unrolled_vector_op(self, ptr: str, n: str, scale: float) -> List[RVVInstruction]:
        self.emit("# Unrolled vector operation with software pipelining")
        self.emit("mv", "t0", ptr)
        self.emit("srai", "t1", n, "3")
        self.emit("andi", "t2", n, "7")
        self.emit("vmv", "v0", "zero")
        self.emit("vmv", "v1", "zero")
        self.emit("vmv", "v2", "zero")
        self.emit("vmv", "v3", "zero")
        self.emit("vmv", "v4", "zero")
        self.emit("vmv", "v5", "zero")
        self.emit("vmv", "v6", "zero")
        self.emit("vmv", "v7", "zero")
        self.emit("pipeline_start:")
        self.emit("vle32.v", "v8", "(t0)")
        self.emit("vle32.v", "v9", "32(t0)")
        self.emit("vle32.v", "v10", "64(t0)")
        self.emit("vle32.v", "v11", "96(t0)")
        self.emit("vfmul.vv", "v12", "v8", "v8")
        self.emit("vfmul.vv", "v13", "v9", "v9")
        self.emit("vfmul.vv", "v14", "v10", "v10")
        self.emit("vfmul.vv", "v15", "v11", "v11")
        self.emit("vfadd.vv", "v0", "v0", "v12")
        self.emit("vfadd.vv", "v1", "v1", "v13")
        self.emit("vfadd.vv", "v2", "v2", "v14")
        self.emit("vfadd.vv", "v3", "v3", "v15")
        self.emit("addi", "t0", "t0", "128")
        self.emit("addi", "t1", "t1", "-1")
        self.emit("bgtz", "t1", "pipeline_start")
        self.emit("vfadd.vv", "v0", "v0", "v1")
        self.emit("vfadd.vv", "v0", "v0", "v2")
        self.emit("vfadd.vv", "v0", "v0", "v3")
        self.emit("vse32.v", "v0", "(t2)")
        return self.instructions

    def generate_reduce_sum(self, ptr: str, n: str) -> List[RVVInstruction]:
        self.emit("# Vector reduction sum with RVV")
        self.emit("mv", "t0", ptr)
        self.emit("srai", "t1", n, "3")
        self.emit("vmv", "v0", "zero")
        self.emit("li", "t2", "8")
        self.emit("reduce_loop:")
        self.emit("vsetvl", "t3", "t2", "8")
        self.emit("vle32.v", "v1", "(t0)")
        self.emit("vfadd.vv", "v0", "v0", "v1")
        self.emit("addi", "t0", "t0", "32")
        self.emit("addi", "t1", "t1", "-1")
        self.emit("bgtz", "t1", "reduce_loop")
        self.emit("vmv.x.s", "t0", "v0")
        return self.instructions

    def get_assembly(self) -> str:
        lines = []
        for instr in self.instructions:
            if str(instr).startswith("#"):
                lines.append(str(instr))
            else:
                lines.append(f"    {instr}")
        return "\n".join(lines)


def generate_rvv_asm(op_type: str, ptrs: Dict[str, str], sizes: Dict[str, str]) -> str:
    codegen = RVVVectorCodeGen()

    if op_type == "dot_product":
        codegen.generate_dot_product(ptrs["a"], ptrs["b"], ptrs["c"], sizes["n"])
    elif op_type == "matrix_multiply":
        codegen.generate_matrix_multiply(ptrs["A"], ptrs["B"], ptrs["C"], sizes["M"], sizes["N"], sizes["K"])
    elif op_type == "vector_scale":
        codegen.generate_unrolled_vector_op(ptrs["x"], sizes["n"], float(sizes.get("scale", "1.0")))
    elif op_type == "reduce_sum":
        codegen.generate_reduce_sum(ptrs["x"], sizes["n"])

    return codegen.get_assembly()


def get_vrv_intrinsic_patterns() -> Dict[str, str]:
    return {
        "vle32_v": "Vector load 32-bit: vle32.v vd, (rs1)",
        "vse32_v": "Vector store 32-bit: vse32.v vs2, (rs1)",
        "vfmul_vv": "Vector float multiply: vfmul.vv vd, vs2, vs1",
        "vfadd_vv": "Vector float add: vfadd.vv vd, vs2, vs1",
        "vfmacc_vv": "Vector float multiply-accumulate: vfmacc.vv vd, vs2, vs1",
        "vfsub_vv": "Vector float subtract: vfsub.vv vd, vs2, vs1",
        "vfdiv_vv": "Vector float divide: vfdiv.vv vd, vs2, vs1",
        "vfsqrt_v": "Vector float sqrt: vfsqrt.v vd, vs2",
        "vfmul_vf": "Vector float multiply by scalar: vfmul.vf vd, vs2, rs1",
        "vfadd_vf": "Vector float add scalar: vfadd.vf vd, vs2, rs1",
    }


@dataclass
class PrecisionContext:
    frm: str = "rne"
    fflags: str = "zero"
    exact_order: bool = True
    preserve_nan: bool = True
    no_subnormals: bool = False

    def get_rounding_mode(self) -> str:
        return self.frm

    def enable_strict_fp(self):
        self.frm = "rne"
        self.exact_order = True
        self.preserve_nan = True
        self.no_subnormals = True

    def relaxed_fp(self):
        self.frm = "dyn"
        self.exact_order = False
        self.preserve_nan = False
        self.no_subnormals = False


def apply_precision_control(asm_lines: List[str], ctx: PrecisionContext) -> List[str]:
    result = []
    for line in asm_lines:
        if line.strip().startswith("vfmul") or line.strip().startswith("vfadd"):
            result.append(f"    fsrm {ctx.frm}")
            result.append(line)
            result.append("    csrr zero, fflags")
        else:
            result.append(line)
    return result


class FPRoundingMode:
    RNE = "rne"
    RTZ = "rtz"
    RDN = "rdn"
    RUP = "rup"
    RMM = "rmm"
    DYN = "dyn"


@dataclass
class FPAccuracyConfig:
    strict_order: bool = True
    preserve_sign: bool = True
    no_nan_boxing: bool = True
    exact_flag_propagation: bool = True
    rounding_mode: str = FPRoundingMode.RNE
    allow_subnormals: bool = False
    fflags_check_every_op: bool = True

    def get_fsrm(self) -> str:
        if self.rounding_mode == FPRoundingMode.RNE:
            return "000"
        elif self.rounding_mode == FPRoundingMode.RTZ:
            return "001"
        elif self.rounding_mode == FPRoundingMode.RDN:
            return "010"
        elif self.rounding_mode == FPRoundingMode.RUP:
            return "011"
        elif self.rounding_mode == FPRoundingMode.RMM:
            return "100"
        return "111"


class StrictFP32Accuracy:
    def __init__(self):
        self.config = FPAccuracyConfig()
        self.ordered_ops: List[Tuple[str, str, str, str]] = []
        self.nan_check_count = 0
        self.subnormal_count = 0
        self.rounding_count = 0

    def record_op(self, op_type: str, dest: str, src1: str, src2: str):
        self.ordered_ops.append((op_type, dest, src1, src2))

    def verify_order(self) -> bool:
        if not self.config.strict_order:
            return True
        seen: Set[str] = set()
        for op_type, dest, src1, src2 in self.ordered_ops:
            if src1 in seen and src2 in seen:
                return False
            seen.add(dest)
        return True

    def check_nan(self, value: str) -> bool:
        if not self.config.preserve_sign:
            return True
        return True

    def get_precision_overhead(self) -> int:
        overhead = 0
        if self.config.fflags_check_every_op:
            overhead = len(self.ordered_ops) * 2
        if self.config.strict_order:
            overhead += len(self.ordered_ops)
        return overhead

    def estimate_accuracy_loss(self) -> float:
        loss = 0.0
        if not self.config.strict_order:
            loss += 0.001
        if self.config.allow_subnormals:
            loss += 0.0001
        loss += self.rounding_count * 0.00001
        return min(loss, 1.0)

    def get_final_accuracy(self) -> float:
        """启发式占位，非测量值。"""
        baseline = 0.70
        improvement = 1.0 - baseline
        loss = self.estimate_accuracy_loss()
        return min(0.99, baseline + improvement * (1.0 - loss))


def generate_strict_fp32_asm(op_type: str, ptrs: Dict[str, str], sizes: Dict[str, str]) -> str:
    codegen = RVVVectorCodeGen()
    fp_control = StrictFP32Accuracy()
    fp_control.config.strict_order = True
    fp_control.config.fflags_check_every_op = True
    fp_control.config.rounding_mode = FPRoundingMode.RNE

    asm_lines = []

    if op_type == "dot_product":
        asm_lines.append("    # Strict FP32 dot product with RVV")
        asm_lines.append("    # Rounding mode: RNE (round to nearest, ties to even)")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    mv t0, a0")
        asm_lines.append("    mv t1, a1")
        asm_lines.append("    mv t2, a2")
        asm_lines.append("    srai t3, a3, 3")
        asm_lines.append("    andi t4, a3, 7")
        asm_lines.append("    li t5, 8")
        asm_lines.append("    vmv.v.i v0, zero")
        asm_lines.append("    vmv.v.i v1, zero")
        asm_lines.append("    vmv.v.i v2, zero")
        asm_lines.append("    vmv.v.i v3, zero")
        asm_lines.append("    blez t3, .Lstrict_remainder")
        asm_lines.append(".Lstrict_main:")
        asm_lines.append("    vsetvl t6, t5, 8")
        asm_lines.append("    vle32.v v8, (t0)")
        asm_lines.append("    vle32.v v9, (t1)")
        asm_lines.append("    csrr t6, fflags")
        asm_lines.append("    vfmul.vv v10, v8, v9")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    csrr zero, fflags")
        asm_lines.append("    vfadd.vv v0, v0, v10")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    csrr zero, fflags")
        asm_lines.append("    addi t0, t0, 128")
        asm_lines.append("    addi t1, t1, 128")
        asm_lines.append("    addi t3, t3, -8")
        asm_lines.append("    bgtz t3, .Lstrict_main")
        asm_lines.append(".Lstrict_remainder:")
        asm_lines.append("    blez t4, .Lstrict_done")
        asm_lines.append(".Lstrict_rem_loop:")
        asm_lines.append("    addi t4, t4, -1")
        asm_lines.append("    flw fa0, (t0)")
        asm_lines.append("    flw fa1, (t1)")
        asm_lines.append("    fmul.s fa2, fa0, fa1")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    fadd.s fa3, fa3, fa2")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    addi t0, t0, 4")
        asm_lines.append("    addi t1, t1, 4")
        asm_lines.append("    bgtz t4, .Lstrict_rem_loop")
        asm_lines.append(".Lstrict_done:")
        asm_lines.append("    vmv.x.s t0, v0")
        asm_lines.append("    fmv.x.w t1, fa3")
        asm_lines.append("    addw t0, t0, t1")
        asm_lines.append("    sw t0, (a0)")
        fp_control.record_op("vfmul", "v10", "v8", "v9")
        fp_control.record_op("vfadd", "v0", "v0", "v10")

    elif op_type == "matrix_multiply":
        asm_lines.append("    # Strict FP32 matrix multiply with RVV")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    mv t0, a0")
        asm_lines.append("    mv t1, a1")
        asm_lines.append("    mv t2, a2")
        asm_lines.append("    li t3, 8")
        asm_lines.append("    outer_loop:")
        asm_lines.append("    mv t4, t1")
        asm_lines.append("    li t5, 8")
        asm_lines.append("    inner_loop:")
        asm_lines.append("    vsetvl t6, t3, 8")
        asm_lines.append("    vle32.v v0, (t0)")
        asm_lines.append("    vle32.v v1, (t4)")
        asm_lines.append("    csrr t6, fflags")
        asm_lines.append("    vfmul.vv v2, v0, v1")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    csrr zero, fflags")
        asm_lines.append("    vfadd.vv v3, v3, v2")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    vse32.v v3, (t2)")
        asm_lines.append("    addi t4, t4, 32")
        asm_lines.append("    addi t5, t5, -1")
        asm_lines.append("    bgtz t5, inner_loop")
        asm_lines.append("    addi t0, t0, 32")
        asm_lines.append("    addi t2, t2, 32")
        asm_lines.append("    addi t3, t3, -1")
        asm_lines.append("    bgtz t3, outer_loop")
        fp_control.record_op("vfmul", "v2", "v0", "v1")
        fp_control.record_op("vfadd", "v3", "v3", "v2")

    elif op_type == "vector_scale":
        asm_lines.append("    # Strict FP32 vector scale with RVV")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    mv t0, a0")
        asm_lines.append("    srai t1, a1, 2")
        asm_lines.append("    andi t2, a1, 3")
        asm_lines.append("    li t3, 8")
        asm_lines.append(".Lstrict_scale_main:")
        asm_lines.append("    vsetvl t6, t3, 8")
        asm_lines.append("    vle32.v v0, (t0)")
        asm_lines.append("    csrr t6, fflags")
        asm_lines.append("    vfmul.vf v1, v0, fa0")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    csrr zero, fflags")
        asm_lines.append("    vse32.v v1, (t0)")
        asm_lines.append("    addi t0, t0, 32")
        asm_lines.append("    addi t1, t1, -1")
        asm_lines.append("    bgtz t1, .Lstrict_scale_main")
        asm_lines.append(".Lstrict_scale_remainder:")
        asm_lines.append("    blez t2, .Lstrict_scale_done")
        asm_lines.append("    flw fa0, (t0)")
        asm_lines.append("    fmul.s fa1, fa0, fa0")
        asm_lines.append("    fsrmi 0")
        asm_lines.append("    fsw fa1, (t0)")
        asm_lines.append("    addi t0, t0, 4")
        asm_lines.append("    addi t2, t2, -1")
        asm_lines.append("    bgtz t2, .Lstrict_scale_remainder")
        asm_lines.append(".Lstrict_scale_done:")
        fp_control.record_op("vfmul", "v1", "v0", "fa0")

    return "\n".join(asm_lines)


def benchmark_rvv_performance() -> Dict[str, float]:
    """占位：真实吞吐/精度需在目标硬件或指定 QEMU 版本上实测后填入。"""
    return {}
