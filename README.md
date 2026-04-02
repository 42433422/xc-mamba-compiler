# JNCC: Just NC Compiler

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Mamba-SSM-orange?style=flat-square" alt="Mamba">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/RISC--V-64--bit-purple?style=flat-square" alt="RISC-V">
</p>

> 🤖 **纯AI编译器** - XC语言 → RISC-V64汇编（无C/IR中间层！）

[![GitHub stars](https://img.shields.io/github/stars/42433422/xc-ai-compile?style=flat-square)](https://github.com/42433422/xc-ai-compile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](https://opensource.org/licenses/MIT)

## 🎯 项目目标

**用Mamba AI直接替代传统编译器后端，实现纯端到端编译！**

```
传统编译器流程（多层级，降低效率）：
  XC → [前端] → AST → [优化] → IR → [后端] → C → [gcc/clang] → 汇编

本项目流程（极简，无任何中间层）：
  XC → [JNCC] → 汇编  ✅ 零依赖！
              ↑
        Mamba AI / Oracle 规则编译器
```

### 核心创新

| 创新点 | 说明 |
|--------|------|
| **零中间层** | 不经过C/IR，直接XC→汇编 |
| **双引擎** | Oracle规则引擎 + Mamba AI推理 |
| **自给自足** | 用Oracle生成训练数据，不依赖gcc/clang |
| **高效推理** | Mamba架构，线性时间复杂度 |

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         JNCC 架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   XC Source ──► Lexer ──► Parser ──► AST                      │
│                                              │                   │
│                         ┌─────────────────────┴─────────────────┤
│                         ▼                                       │
│   ┌────────────────────────────────────────────────────────────┐│
│   │                   四种编译策略                              ││
│   │                                                              ││
│   │   oracle:  纯规则编译器，生成标准RISC-V64汇编               ││
│   │   model:   纯Mamba AI，端到端生成汇编                       ││
│   │   hybrid:  AI生成 + Oracle校验 + 自动修复                  ││
│   │   ir:      中间表示优化管道                                 ││
│   │                                                              ││
│   └────────────────────────────────────────────────────────────┘│
│                         │                                       │
│                         ▼                                       │
│   Output: RISC-V64 GNU Assembly (可运行)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 为什么用Mamba？

| 特性 | Transformer | Mamba |
|------|-------------|-------|
| 复杂度 | O(n²) | **O(n)** |
| 推理速度 | 慢 | **快** |
| 显存占用 | 高 | **低** |
| 代码生成效果 | 好 | **相当/更好** |

## 📁 项目结构

```
jncc/
├── jncc_cli.py                 # ⭐ 统一命令行入口
│
├── compiler/                    # 编译器核心
│   ├── jncc_pipeline.py        # 编译管道（4种策略）
│   ├── jncc_model_infer.py     # Mamba AI推理
│   ├── jncc_ir_v0.py          # IR定义与转换
│   ├── jncc_ir_opt.py         # IR优化遍
│   ├── jncc_peephole_asm.py   # 汇编窥孔优化
│   ├── jncc_asm_norm.py       # 汇编规范化/对比
│   └── jncc_eval_metrics.py   # 评估指标
│
├── xc_asm_oracle.py           # 🔑 RISC-V64 Oracle规则编译器
├── xc_asm_validate.py        # 汇编校验
│
├── dataset/                    # 数据集
│   ├── xc_asm_synth.py       # XC程序随机生成器
│   ├── jncc_corpus_presets.py # 预设测试用例
│   └── xc_asm_train.jsonl    # 训练数据 (100条)
│
├── training/                   # 训练
│   └── train_xc_mamba.py      # Mamba微调脚本
│
├── tests/                     # 测试
└── tools/                    # 工具
```

## 🚀 快速开始

### 安装依赖

```bash
pip install torch transformers datasets accelerate
pip install mamba-ssm  # 可选，提升性能
```

### 一键编译

```bash
# Oracle规则编译（无需训练）
python jncc_cli.py compile --xc '# { $x = 10 ^ x }'

# AI模型编译（需要先训练）
python jncc_cli.py compile --backend model --model models/JNCC/final --xc '# { $x = 10 ^ x }'

# 混合模式（AI + Oracle校验）
python jncc_cli.py compile --backend hybrid --model models/JNCC/final --xc '# { $x = 10 ^ x }'
```

### 一键训练

```bash
# 生成训练数据
python run_first_ai_compiler.py prepare --count 100

# 训练Mamba模型
python run_first_ai_compiler.py train --epochs 2 --model mamba-130m

# 评估
python jncc_cli.py bench-oracle --jsonl dataset/xc_asm_test.jsonl --model models/JNCC/final
```

## 📖 XC 语言

### 完整语法

```xc
# 程序入口
{
    # 变量声明
    $x = 10              # 自动推断类型
    $y: int = 20         # 显式类型
    $name = "JNCC"      # 字符串

    # 算术运算
    $sum = x + y
    $prod = x * y
    $div = x / y
    $mod = x % y

    # 比较运算
    ? (x > y) {          # if
        ! "x > y"
    } ?: {               # else
        ! "x <= y"
    }

    # 循环
    ~i = 0; i < 10; i = i + 1 {
        ! i
    }

    @ (x > 0) {         # while
        x = x - 1
    }

    # 函数
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
| `% func` | 函数定义 | `% add(a, b) -> int { ... }` |
| `^` | 返回值 | `^ a + b` |
| `? (cond) { }` | if条件 | `? (x > 0) { ... }` |
| `?: { }` | else分支 | `?: { ... }` |
| `?? (cond) { }` | else if | `?? (x < 0) { ... }` |
| `@ (cond) { }` | while循环 | `@ (i < 10) { ... }` |
| `~i=0; i<n; i++ { }` | for循环 | `~i=0; i<10; i=i+1 { ... }` |
| `>` | break | `>` |
| `<` | continue | `<` |
| `! x` | 打印 | `! "hello"`, `! x` |
| `& Point { }` | 结构体 | `& Point { x: int; y: int; }` |
| `@PI = 3.14` | 常量 | `@PI = 3.14` |

### Oracle支持的操作

| 类别 | 支持的操作 |
|------|-----------|
| 算术 | `+`, `-`, `*`, `/`, `%` |
| 比较 | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| 逻辑 | `&&`, `\|\|`, `!` |
| 位运算 | `&`, `\|`, `^`, `<<`, `>>`, `~` |
| 控制流 | `if/else`, `while`, `for`, `return` |
| 函数 | 定义、调用、递归 |
| 内存 | `malloc`, `free`, 指针操作 |
| 结构体 | 字段访问、位域 |

## 🔬 技术细节

### 编译策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `oracle` | 纯规则编译 | 确定性场景，高性能 |
| `model` | 纯AI编译 | 探索性代码生成 |
| `hybrid` | AI+Oracle校验 | 平衡质量与覆盖 |
| `ir` | IR优化管道 | 需要深度优化的代码 |

### 训练配置

```bash
python run_first_ai_compiler.py train \
    --model mamba-130m \      # 130M/370M参数
    --epochs 2 \
    --batch_size 2 \
    --lr 2e-4 \
    --phase mix \              # base/feature/mix
    --hierarchical             # 层级注意力
```

### 数据集统计

```
训练集: 90条 (easy: 59, medium: 25, hard: 6)
验证集: 5条
测试集: 5条

语法覆盖: for, while, if, func_call, arith, compare, malloc, pointer...
```

## 📊 评估指标

```bash
python jncc_cli.py bench-oracle --jsonl dataset/xc_asm_test.jsonl
```

输出示例：
```json
{
  "rows_total": 5,
  "oracle_ok_subset": 5,
  "pred_nonempty_compared": 5,
  "normalized_equal_vs_gold": 4,
  "assemble_pass_on_pred": 5,
  "oracle_match_rate": 0.8
}
```

## 🎯 路线图

- [x] XC语言完整词法/语法分析
- [x] RISC-V64 Oracle规则编译器
- [x] Mamba AI微调框架
- [x] 四种编译策略 (oracle/model/hybrid/ir)
- [x] 100+训练数据生成
- [ ] RLHF微调提升质量
- [ ] 多ISA支持 (x86, ARM)
- [ ] JIT编译支持

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📚 参考

- [Mamba: Linear-Time Sequence Modeling](https://arxiv.org/abs/2312.00752)
- [RISC-V ISA Specification](https://riscv.org/technical/specifications/)
- [State Space Models for Language Modeling](https://arxiv.org/abs/2312.00752)
