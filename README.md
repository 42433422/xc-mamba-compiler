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

### Model Performance (10-sample validation set)

| Metric | Value | Source |
|---|---|---|
| Oracle runtime correctness | **100%** | `reports/linux_exec_validate_from_pred_model_all_optimized.json` |
| Model prediction runtime correctness | **70%** | `reports/linux_exec_validate_from_pred_model_all_optimized.json` |
| Runtime match rate | **50%** | `reports/linux_exec_validate_from_pred_model_all_optimized.json` |
| Mean generation time | **44.36s/sample** | `reports/pred_asm_model_from_host_all_optimized.jsonl` |
| Median generation time | **44.16s/sample** | `reports/pred_asm_model_from_host_all_optimized.jsonl` |

### Oracle vs Model Comparison

| Metric | Oracle | Model | Ratio |
|---|---|---|---|
| Runtime correctness | 100% | 70% | Gap: 30% |
| Mean latency | ~0.0016s | 44.36s | Model ~27,725x slower |

Notes:
- Oracle uses deterministic rule-based compilation
- Model uses fine-tuned Mamba-130M SSM with LoRA + ORPO training
- Generation latency measured on local GPU (host)

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
| Runtime equivalence on real RISC-V execution | Passed | 100% oracle, 70% model (10 samples). |

## Roadmap

### Completed

- [x] XC lexer and parser
- [x] RISC-V64 Oracle backend
- [x] Mamba fine-tuning pipeline
- [x] Multi-backend compiler strategy (`oracle` / `model` / `hybrid` / `ir`)
- [x] Initial synthetic XC→ASM dataset generation
- [x] End-to-end runtime correctness validation on Linux/qemu-riscv64

### Future Development: Two-Layer Dynamic Compilation

We are exploring a hybrid architecture to combine SSM speed with LLM accuracy:

#### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│              Two-Layer Dynamic Compilation Pipeline                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │           Layer 1: Fast SSM Inference (Mamba)                  │ │
│  │                                                                │ │
│  │   XC Source ──► Assembly IR Candidate ──► Validation ──► Set  │ │
│  │                          │                      │               │ │
│  │                          ▼                      ▼               │ │
│  │                   ┌─────────────────┐    ┌──────────────┐     │ │
│  │                   │ Dedicated Test   │    │ Confidence   │     │ │
│  │                   │ Suite (Oracle)   │    │ Scoring      │     │ │
│  │                   └─────────────────┘    └──────────────┘     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                               │                                        │
│                               │ Pass Validation                         │
│                               │ Low Confidence                          │
│                               ▼                                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │           Layer 2: Large Language Model Refinement             │ │
│  │                                                                │ │
│  │   Validated Assembly IR ──► LLM (GPT-4/Claude) ──► Output    │ │
│  │                              │                                  │ │
│  │                              ▼                                  │ │
│  │                    ┌─────────────────┐                         │ │
│  │                    │ Re-validation   │                         │ │
│  │                    │ + Natural Lang  │                         │ │
│  │                    │ Specification   │                         │ │
│  │                    └─────────────────┘                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Dual-Model Division of Labor

| Model | Role | Strengths |
|-------|------|-----------|
| **Mamba SSM** | Fast generation of Assembly IR candidates | Low latency, high throughput |
| **Large LLM** | Verification, correction, optimization | Strong reasoning, natural language understanding |

#### Dynamic Routing Mechanism

```
SSM Output ──► Confidence Score ──►
                                    ├── High (>0.8) ──► Direct Output
                                    ├── Medium ──► LLM Verification ──► Output
                                    └── Low (<0.5) ──► LLM Correction ──► Re-validation ──► Output
```

#### Neural-Inspired Adaptation (Long-term Goal)

Map neural dynamic mechanisms to compiler adaptation:

| Neural Mechanism | Mathematical Model | Compiler Application |
|-----------------|-------------------|---------------------|
| Membrane potential dynamics | `dV/dt = (V_rest - V)/τ + I` | Confidence threshold adaptation |
| Spike-timing plasticity | `Δw = η · (pre · post - θ)` | Validation failure → model update |
| Homeostatic regulation | `w_i = w_i / Σw_j` | Confidence score normalization |

#### Research Objectives

1. **Hybrid Compilation Pipeline**: Combine SSM speed with LLM accuracy
2. **Dynamic Model Routing**: Automatically select inference path based on task complexity
3. **Self-Evolution**: Use validation failures to iteratively improve both models
4. **Cross-Architecture Support**: Extend framework to x86-64, ARM via transfer learning
5. **Neural-Inspired Adaptation**: Implement biologically-motivated adaptation mechanisms

#### Technical Challenges

| Challenge | Description | Mitigation |
|-----------|-------------|------------|
| Latency | LLM inference is slow (~seconds vs ms) | Cache frequent patterns; async pipeline |
| Consistency | LLM may introduce semantic changes | Mandatory validation after LLM step |
| Training Data | Need paired (IR, Assembly) data | Synthetic data generation with oracle |
| Biological Plausibility | Neural models are simplifications | Use established computational neuroscience frameworks |

#### Expected Outcomes

- **Runtime Correctness**: 70% → 90%+ via LLM verification
- **Latency**: Maintain <100ms for 80% of simple cases via SSM direct output
- **Adaptability**: Support new architectures with minimal fine-tuning
- **Self-Tuning**: Automatic confidence threshold adjustment based on validation feedback

#### Implementation Roadmap

```
Phase 1: Mathematical Modeling
  └── Formalize neural dynamics as adaptation functions

Phase 2: Integration
  └── Embed adaptive mechanisms into AI compiler

Phase 3: Self-Evolution
  └── Implement feedback loop: validation → update → retrain

Phase 4: Auto-Adaptation
  └── Achieve self-tuning compilation without manual intervention
```

### Planned

- [ ] Two-layer dynamic compilation with LLM refinement
- [ ] Dynamic model routing based on confidence scoring
- [ ] Self-evolution via validation feedback loop
- [ ] Multi-ISA support (x86/ARM)
- [ ] JIT-oriented runtime path
- [ ] Larger-scale training data and model scaling

## License

MIT License. See [LICENSE](LICENSE).

## Contributing

Issues and pull requests are welcome.

## References

- [Mamba: Linear-Time Sequence Modeling with Selective State Spaces](https://arxiv.org/abs/2312.00752)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
- [LLMA: Towards LLVM Inference with LLMs](https://arxiv.org/)