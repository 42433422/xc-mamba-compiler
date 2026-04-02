#!/usr/bin/env python3
"""
RISC-V 汇编执行验证器
在 Linux 上使用 riscv64-linux-gnu-gcc 和 qemu-riscv64 进行真实执行测试

用法:
    python linux_exec_test.py

依赖 (Linux):
    sudo apt install gcc-riscv64-linux-gnu qemu-user
"""

import json
import subprocess
import tempfile
import os
import sys
import re
from pathlib import Path

def check_dependencies():
    """检查必要的工具是否安装"""
    tools = ['riscv64-linux-gnu-gcc', 'riscv64-linux-gnu-as', 'qemu-riscv64']
    missing = []

    for tool in tools:
        result = subprocess.run(f'which {tool}', shell=True, capture_output=True)
        if result.returncode != 0:
            missing.append(tool)

    if missing:
        print(f"❌ 缺少依赖: {', '.join(missing)}")
        print("请运行: sudo apt install gcc-riscv64-linux-gnu qemu-user")
        return False
    return True

def compile_and_run(asm_code, timeout=5):
    """
    编译RISC-V汇编并使用QEMU执行
    返回: (exit_code, stdout, stderr)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        asm_file = Path(tmpdir) / 'test.s'
        exe_file = Path(tmpdir) / 'test'

        # 写入汇编文件
        asm_file.write_text(asm_code)

        # 编译
        compile_result = subprocess.run(
            ['riscv64-linux-gnu-gcc', '-o', str(exe_file), str(asm_file)],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if compile_result.returncode != 0:
            return None, None, f"编译失败: {compile_result.stderr}"

        # 执行
        run_result = subprocess.run(
            ['qemu-riscv64', str(exe_file)],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return run_result.returncode, run_result.stdout, run_result.stderr

def extract_return_value(asm_code):
    """从汇编代码提取预期的返回值"""
    # 找到所有 li a0, N 指令
    pattern = r'li\s+a0,\s*(-?\d+)'
    matches = re.findall(pattern, asm_code)
    if matches:
        # 最后一个li a0通常是返回值
        return int(matches[-1])
    return None

def main():
    print("=" * 70)
    print("JNCC AI编译器 - Linux执行验证")
    print("=" * 70)

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 读取测试数据
    test_file = 'dataset/xc_asm_test.jsonl'
    if not os.path.exists(test_file):
        print(f"❌ 找不到测试文件: {test_file}")
        sys.exit(1)

    with open(test_file) as f:
        test_cases = [json.loads(line) for line in f]

    print(f"📋 测试用例总数: {len(test_cases)}")
    print("=" * 70)

    results = []
    passed = 0
    failed = 0
    errors = 0

    for i, tc in enumerate(test_cases):
        tc_id = tc['id']
        xc_code = tc['xc_source'].replace('\n', ' ')[:50]
        oracle_asm = tc['asm_riscv64']

        print(f"\n【{i+1}/{len(test_cases)}】 {tc_id}")
        print(f"  XC: {xc_code}...")

        # 预期返回值
        expected = extract_return_value(oracle_asm)
        print(f"  预期返回值: {expected}")

        # 用QEMU执行Oracle生成的汇编
        print(f"  执行Oracle汇编...")
        oracle_exit, oracle_out, oracle_err = compile_and_run(oracle_asm)

        if oracle_exit is None:
            print(f"  ⚠️ Oracle编译失败: {oracle_err}")
            errors += 1
            results.append({'id': tc_id, 'status': 'error', 'expected': expected, 'actual': None})
            continue

        oracle_return = oracle_exit
        print(f"  Oracle返回值: {oracle_return}")

        # 对比结果
        if oracle_return == expected:
            print(f"  ✅ 通过")
            passed += 1
            status = 'pass'
        else:
            print(f"  ❌ 失败 (exit={oracle_return}, expected={expected})")
            failed += 1
            status = 'fail'

        results.append({
            'id': tc_id,
            'status': status,
            'expected': expected,
            'actual': oracle_return
        })

    # 汇总
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)
    print(f"总测试数: {len(results)}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    print(f"错误: {errors} ⚠️")
    print(f"通过率: {passed/len(results)*100:.1f}%")

    if passed == len(results):
        print("\n🎉 所有测试通过！Oracle规则编译器工作正常！")

    # 保存结果
    result_file = 'reports/linux_exec_results.json'
    os.makedirs('reports', exist_ok=True)
    with open(result_file, 'w') as f:
        json.dump({
            'summary': {
                'total': len(results),
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'pass_rate': f"{passed/len(results)*100:.1f}%"
            },
            'details': results
        }, f, indent=2)

    print(f"\n结果已保存到: {result_file}")

if __name__ == '__main__':
    main()
