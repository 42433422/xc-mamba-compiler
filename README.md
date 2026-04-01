# XC AI Compiler

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Mamba-SSM-orange?style=flat-square" alt="Mamba">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/RISC--V-64--bit-purple?style=flat-square" alt="RISC-V">
</p>

> 🤖 **纯AI编译器** - XC语言 → Mamba → RISC-V64汇编（无C中间层！）

## 🎯 这是什么项目？

**目标：用AI直接替代传统编译器后端！**

```
传统编译器流程：
  XC → [前端] → AST → [后端] → C → [gcc/clang] → 汇编

本项目流程：
  XC → [前端] → AST → [Mamba AI] → 汇编  ✅ 无C依赖！
                    ↑
            用自研Oracle生成训练数据
```

### 核心创新

1. **自研 RISC-V64 Oracle** - 不依赖 gcc/clang，用规则编译器生成"标准答案"
2. **Mamba 架构** - 比 Transformer 更高效的线性时间模型
3. **端到端** - XC → 汇编，一步到位

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       XC AI Compiler                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   XC Source ──► [Lexer] ──► [Parser] ──► AST                   │
│                                              │                   │
│                         ┌─────────────────────┴─────────────────┤
│                         │                                         │
│                         ▼                                         │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │              两条编译路径                                    │ │
│   │                                                              │ │
│   │   路径1: 传统编译器 (参考实现)                                │ │
│   │   XC ──► xc_compiler.py ──► C / Rust / Mojo              │ │
│   │                                                              │ │
│   │   路径2: AI编译器 (本项目核心)                                │ │
│   │   XC ──► Mamba 模型 ──► RISC-V64 汇编 ⚡                   │ │
│   │         ↑                                                   │ │
│   │         └── 训练数据由 Oracle 生成                           │ │
│   │                                                              │ │
│   └────────────────────────────────────────────────────────────┘ │
│                         │                                         │
│                         ▼                                         │
│   Output: RISC-V64 GNU Assembly (纯AI生成)                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
xc-ai-compiler/
│
├── xc_compiler.py          # XC语言编译器 (XC → C/Rust/Mojo)
├── xc_preprocess.py        # 预处理模块
│
├── xc_asm_oracle.py        # 🔑 RISC-V64 Oracle (规则编译器)
│                            #    不依赖gcc/clang，直接生成汇编
│
├── xc_asm_validate.py      # 汇编校验工具
│
├── dataset/                # 训练数据
│   ├── build_xc_asm_corpus.py   # 数据生成器
│   ├── xc_asm_synth.py           # 随机XC程序生成
│   └── xc_asm_train.jsonl        # 训练数据 (XC ↔ 汇编配对)
│
├── training/               # 训练脚本
│   └── train_xc_mamba.py       # Mamba微调入口
│
├── inference/             # 推理脚本
│   └── xc_compile_ml.py        # AI编译器推理
│
├── run_first_ai_compiler.py    # 一键训练脚本
│
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install torch transformers datasets accelerate
```

### 2. 一键训练

```bash
# Step 1: 生成训练数据 (XC ↔ 汇编配对)
python run_first_ai_compiler.py prepare --count 500

# Step 2: Mamba微调
python run_first_ai_compiler.py train --epochs 2 --model mamba-130m

# Step 3: 推理测试
python inference/xc_compile_ml.py --model models/JNCC/final --xc '# { $x = 10 ^ x }'
```

### 3. Oracle对照（无需训练）

```bash
python run_first_ai_compiler.py demo
```

## 📖 XC 语言示例

```xc
# 程序入口
{
    $x: int = 10
    $y: int = 20
    $sum: int = x + y

    % add(a: int, b: int) -> int {
        ^ a + b
    }

    ^ add(x, y)
}
```

### 语法速查

| XC符号 | 含义 | 示例 |
|--------|------|------|
| `# { }` | 程序入口 | `# { ... }` |
| `$x` | 变量声明 | `$x = 10` |
| `$x: int` | 显式类型 | `$x: int = 10` |
| `% func` | 函数定义 | `% add(a, b) { ... }` |
| `^` | 返回 | `^ a + b` |
| `? (cond) { }` | 条件 | `? (x > 0) { ... }` |
| `@ (cond) { }` | while循环 | `@ (i < 10) { ... }` |
| `~i=0; i<10; i++ { }` | for循环 | `~i=0; i<10; i=i+1 { ... }` |

## 🔬 技术细节

### 为什么用 Mamba？

| 特性 | Transformer | Mamba |
|------|-------------|-------|
| 复杂度 | O(n²) | **O(n)** |
| 推理速度 | 慢 | **快** |
| 显存占用 | 高 | **低** |
| 代码生成效果 | 好 | **相当/更好** |

### Oracle 支持的 XC 子集

- 变量声明与赋值
- 算术运算 (+, -, *, /, %)
- 逻辑运算 (&&, ||, !)
- 比较运算 (==, !=, <, >, <=, >=)
- 条件分支 (if/else)
- 循环 (while/for)
- 函数定义与调用
- return 语句

### 训练参数

```bash
python run_first_ai_compiler.py train \
    --model mamba-130m \      # 或 mamba-370m
    --epochs 2 \
    --batch_size 2 \
    --lr 2e-4 \
    --phase mix               # 课程学习: base/feature/mix
```

## 🎯 路线图

- [x] XC语言编译器 (XC → C/Rust/Mojo)
- [x] RISC-V64 Oracle 规则后端
- [x] Mamba 微调框架
- [x] 数据生成器
- [ ] 支持更多 XC 语法
- [ ] RLHF 微调提升质量
- [ ] 多目标 ISA 支持

## 📄 许可证

MIT License

## 📚 参考

- [Mamba: Linear-Time Sequence Modeling](https://arxiv.org/abs/2312.00752)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
