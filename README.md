# XC Mamba Compiler

<div align="center">

🤖 **AI驱动的XC语言编译器** | XC语言 → Transformer/Mamba → RISC-V64 Assembly

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-orange?style=flat-square&logo=pytorch)](https://pytorch.org)
[![RISC-V](https://img.shields.io/badge/RISC--V-64--bit-purple?style=flat-square)](https://riscv.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](https://opensource.org/licenses/MIT)

</div>

---

## 📖 简介

XC Mamba Compiler 是一个纯AI驱动的编译器项目，将自研的XC编程语言编译为RISC-V64汇编代码。项目采用Transformer和Mamba架构，实现从源代码到目标代码的端到端生成。

### 核心特性

- 🎯 **纯AI编译** - 无传统编译器后端，AI模型直接生成目标代码
- ⚡ **自研RISC-V Oracle** - 独立规则编译器生成训练标签，不依赖GCC/Clang
- 🔄 **多目标代码生成** - 支持 C / Rust / Mojo / RISC-V64 汇编输出
- 🧪 **可复现实验** - 完整的数据生成、训练、评估流程
- 📊 **层级注意力架构** - 针对程序结构优化的Transformer/Mamba设计

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        XC AI Compiler                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   XC Source ──► [Lexer] ──► [Parser] ──► AST                   │
│                                              │                   │
│                                              ▼                   │
│   ┌────────────────────────────────────────────────────────┐   │
│   │                   数据工厂 (Data Factory)                │   │
│   │  ┌─────────────┐    ┌─────────────────────────────┐  │   │
│   │  │ Random XC   │───►│ RISC-V64 Oracle (规则编译器)  │  │   │
│   │  │ Generator   │    │ 生成Ground Truth汇编         │  │   │
│   │  └─────────────┘    └─────────────────────────────┘  │   │
│   └────────────────────────────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│   ┌────────────────────────────────────────────────────────┐   │
│   │           Hierarchical Transformer / Mamba             │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │   │
│   │  │ Token    │  │Function  │  │Program   │  │Assembly│  │   │
│   │  │ Embedding│  │Attention │  │Attention│  │Decoder │  │   │
│   │  └──────────┘  └──────────┘  └──────────┘  └────────┘  │   │
│   └────────────────────────────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│   Output: Assembly / C / Rust / Mojo                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
xc-mamba-compiler/
├── compiler/              # 编译器核心模块
│   ├── xc_compiler.py     # XC语言编译器 (XC → C/Rust/Mojo)
│   ├── x_compiler.py      # 简化版XC编译器
│   ├── xc_preprocess.py   # 预处理模块
│   ├── xc_asm_oracle.py   # RISC-V64 Oracle (规则编译器)
│   ├── xc_asm_config.py   # 工具链配置
│   ├── xc_translate.py    # AI翻译推理脚本
│   ├── x_language.py      # 项目启动器
│   ├── jncc_*.py          # JNCC评估与优化模块
│   └── AI_Compiler_Roadmap.md
│
├── dataset/               # 数据集目录
│   ├── dataset_builder.py
│   ├── xc_asm_synth.py
│   └── generate_xc_dataset.py
│
├── training/              # 训练脚本
│   ├── train_xc_mamba.py  # Mamba架构训练
│   ├── train_xc_translator.py
│   ├── train_xc_lora.py
│   └── xc_asm_rlhf.py     # RLHF微调
│
├── inference/             # 推理模块
│   ├── translator.py
│   └── x_translate.py
│
├── tools/                 # 工具脚本
│   ├── jncc_research_eval.py
│   ├── benchmark_neuro_ddd_performance.py
│   └── docker_verify_riscv_rvv.sh
│
├── tests/                 # 测试用例
│   └── test_jncc_smoke.py
│
├── wiki/                  # 项目文档
│   ├── Architecture.md
│   ├── XC_Language.md
│   └── Experiments.md
│
└── reports/               # 实验报告
    └── neuro_ddd_benchmark.json
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install torch transformers peft datasets unsloth
```

### 2. 编译XC代码 (传统方式)

```bash
# XC → C
python compiler/xc_compiler.py --input examples/hello.x --target c

# XC → Rust
python compiler/xc_compiler.py --input examples/hello.x --target rust

# XC → RISC-V64 汇编
python compiler/xc_compiler.py --input examples/hello.x --target riscv64
```

### 3. 使用AI翻译器

```bash
# 交互模式
python inference/xc_translate.py --demo

# 文件翻译
python inference/xc_translate.py --input code.x --source x --target rust
```

---

## 📖 XC 语言示例

```xc
# 程序入口
# {
    $x: int = 10
    $y: int = 20
    $sum: int = x + y

    ! "x + y = ", sum

    % add(a: int, b: int) -> int {
        ^ a + b
    }

    ! add(3, 5)

    ? (x > y) {
        ! "x > y"
    } ?: {
        ! "x <= y"
    }

    ~i: int = 0; i < 5; i = i + 1 {
        ! i
    }
}
```

### 语法速查

| XC符号 | 含义 | 示例 |
|--------|------|------|
| `# { }` | 程序入口 | `# { ... }` |
| `$x` | 变量声明 | `$x = 10` |
| `$x: int` | 显式类型 | `$x: int = 10` |
| `@PI` | 常量 | `@PI = 3.14` |
| `% func` | 函数定义 | `% add(a, b) { ... }` |
| `^` | 返回 | `^ a + b` |
| `? (cond) { }` | 条件 | `? (x > 0) { ... }` |
| `?: { }` | else | `?: { ... }` |
| `?? (cond) { }` | else if | `?? (x < 0) { ... }` |
| `@ (cond) { }` | while循环 | `@ (i < 10) { ... }` |
| `~i=0; i<10; i++ { }` | for循环 | `~i=0; i<10; i=i+1 { ... }` |
| `>` | break | `>` |
| `<` | continue | `<` |
| `! x` | 打印 | `! "hello"` |
| `& Point { }` | 结构体 | `& Point { x: int; y: int; }` |

---

## 🔬 训练指南

### 步骤1: 生成训练数据

```python
from compiler.xc_asm_oracle import compile_xc_to_asm_riscv64

# 生成 XC ↔ RISC-V 配对数据
def generate_training_pair():
    xc_code = generate_random_xc_program()
    asm_code = compile_xc_to_asm_riscv64(xc_code)
    return {"xc": xc_code, "asm": asm_code}
```

### 步骤2: 微调模型

```bash
python training/train_xc_mamba.py \
    --model qwen2.5-coder-1.5b \
    --epochs 3 \
    --batch_size 4
```

### 步骤3: 评估

```bash
python tools/jncc_research_eval.py --model models/xc-translator
```

---

## 📊 技术规格

| 组件 | 实现 |
|------|------|
| 词法分析器 | 正则表达式 + 状态机 |
| 语法分析器 | 递归下降解析器 |
| AST | dataclass 树结构 |
| 代码生成器 | C / Rust / Mojo / RISC-V64 |
| Oracle | RV64G 整数子集 |
| 目标ISA | RISC-V 64-bit (RV64GC) |
| AI架构 | Transformer / Mamba |

---

## 🎯 路线图

- [x] XC语言编译器 (XC → C/Rust/Mojo)
- [x] RISC-V64 Oracle 规则后端
- [x] 数据生成器 (100K+ 训练样本)
- [x] Hierarchical Transformer 实现
- [x] Mamba架构支持
- [ ] RLHF 微调
- [ ] 性能优化与量化
- [ ] RISC-V Vector Extension (RVV) 优化

---

## 📚 文档

- [🏛️ 架构文档](wiki/Architecture.md)
- [📝 XC语言规范](XC_GRAMMAR_SPEC.md)
- [📊 实验记录](wiki/Experiments.md)
- [🔧 安装指南](wiki/Installation.md)
- [🛣️ 技术路线图](compiler/AI_Compiler_Roadmap.md)

---

## 🧪 测试

```bash
# 运行单元测试
pytest tests/ -v

# 运行RISC-V验证
bash tools/docker_verify_riscv_rvv.sh
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 📚 参考

- [Transformer: Attention Is All You Need](https://arxiv.org/abs/1706.03762)
- [Mamba: Linear-Time Sequence Modeling](https://arxiv.org/abs/2312.00752)
- [CodeGen: Open Code Generation](https://arxiv.org/abs/2203.13474)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)

---

<div align="center">

**XC Mamba Compiler** - AI驱动的下一代编译器

Made with ❤️ by [42433422](https://github.com/42433422)

</div>
