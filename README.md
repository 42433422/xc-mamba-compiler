# JNCC: Just NC Compiler

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Mamba-SSM-orange?style=flat-square" alt="Mamba">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/RISC--V-64--bit-purple?style=flat-square" alt="RISC-V">
</p>

> 🤖 **AI Compiler Prototype** - XC language → RISC-V64 GNU assembly (no C/IR middle stage in the model path).

[![GitHub stars](https://img.shields.io/github/stars/42433422/xc-mamba-compiler?style=flat-square)](https://github.com/42433422/xc-mamba-compiler)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)

## Overview

JNCC is an experimental AI compiler stack that translates XC source code into RISC-V64 assembly.  
It supports both a deterministic rule-based backend (Oracle) and a learned backend (Mamba model), plus a hybrid validation mode.

Core technology stack: **C/C++**, **compiler theory**, **Mamba model architecture**, **operator-level optimization**, and a **self-designed XC language**.

### Pipeline

```text
Conventional pipeline:
  XC -> Frontend -> AST -> Optimization -> IR -> Backend -> C -> gcc/clang -> Assembly

JNCC pipeline:
  XC -> JNCC -> RISC-V64 Assembly
       (Oracle / Model / Hybrid / IR)
```

## Key Features

| Feature | Description |
|---|---|
| Zero-model middle stage | The model backend generates assembly directly from XC prompts. |
| Dual-engine design | Oracle rules + Mamba model inference. |
| Self-generated supervision | Oracle can generate XC→ASM pairs for training and regression. |
| Multiple backends | `oracle`, `model`, `hybrid`, and `ir`. |

## Quantitative Results

The following values are from the repository's real benchmark artifacts (`reports/compare_jncc_val.json`, generated on local validation set).

| Metric | Value |
|---|---|
| AI assembly pass rate | **100%** (5/5 assembled successfully) |
| Mean model generation time | **52.10 s/sample** |
| Median model generation time | **53.98 s/sample** |
| Mean Oracle compile time | **0.00164 s/sample** |
| Median Oracle compile time | **0.00090 s/sample** |

Derived comparison on the same benchmark scope:
- Model path is **~31,760x slower** than Oracle in mean latency (52.10 / 0.00164).
- Oracle uses rule execution and is currently the low-latency baseline in this repo.

Notes:
- These are real measured values on the current validation setup (`dataset/xc_asm_val.jsonl`, 5 rows).
- A transformer-vs-mamba speed or memory A/B table is not yet committed in this repository.

## Repository Layout

```text
jncc/
├── jncc_cli.py
├── compiler/
│   ├── jncc_pipeline.py
│   ├── jncc_model_infer.py
│   ├── jncc_ir_v0.py
│   ├── jncc_ir_opt.py
│   ├── jncc_peephole_asm.py
│   ├── jncc_asm_norm.py
│   └── jncc_eval_metrics.py
├── xc_asm_oracle.py
├── xc_asm_validate.py
├── dataset/
│   ├── xc_asm_synth.py
│   ├── jncc_corpus_presets.py
│   └── xc_asm_train.jsonl
├── training/
│   └── train_xc_mamba.py
├── reports/
└── tools/
```

## Quick Start

### Install dependencies

```bash
pip install torch transformers datasets accelerate
pip install mamba-ssm
```

### Compile XC

```bash
# Oracle backend (no model required)
python jncc_cli.py compile --xc '# { $x = 10 ^ x }'

# Model backend
python jncc_cli.py compile --backend model --model models/JNCC/final --xc '# { $x = 10 ^ x }'

# Hybrid backend (model + Oracle checks)
python jncc_cli.py compile --backend hybrid --model models/JNCC/final --xc '# { $x = 10 ^ x }'
```

### Train and evaluate

```bash
# Prepare data
python run_first_ai_compiler.py prepare --count 200

# Train Mamba model
python run_first_ai_compiler.py train --epochs 2 --model mamba-130m

# Benchmark against Oracle references
python jncc_cli.py bench-oracle --jsonl dataset/xc_asm_test.jsonl --model models/JNCC/final
```

## XC Language (Example)

```xc
# {
    $x = 10
    $y: int = 20

    $sum = x + y
    $prod = x * y

    ? (x > y) {
        ! "x > y"
    } ?: {
        ! "x <= y"
    }

    ~i = 0; i < 10; i = i + 1 {
        ! i
    }

    @ (x > 0) {
        x = x - 1
    }

    % add(a: int, b: int) -> int {
        ^ a + b
    }

    ^ add(x, y)
}
```

## Current Validation Status

| Item | Status | Note |
|---|---|---|
| XC semantic logic check | Passed | Interpreter-based checks completed. |
| Oracle assembly structure check | Passed | Rule output manually and programmatically validated. |
| Generated assembly syntax | Passed | GNU assembler pass rate on benchmarked predictions: 100%. |
| Runtime equivalence on real RISC-V execution | Pending | Requires Linux + RISC-V toolchain and qemu. |

## Roadmap

- [x] XC lexer and parser
- [x] RISC-V64 Oracle backend
- [x] Mamba fine-tuning pipeline
- [x] Multi-backend compiler strategy (`oracle` / `model` / `hybrid` / `ir`)
- [x] Initial synthetic XC→ASM dataset generation
- [ ] End-to-end runtime correctness validation on Linux/qemu-riscv64
- [ ] Larger-scale training data and model scaling
- [ ] Multi-ISA support (x86/ARM)
- [ ] JIT-oriented runtime path

## License

MIT License. See [LICENSE](LICENSE).

## Contributing

Issues and pull requests are welcome.

## References

- [Mamba: Linear-Time Sequence Modeling](https://arxiv.org/abs/2312.00752)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
