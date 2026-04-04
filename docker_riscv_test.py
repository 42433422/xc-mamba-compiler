#!/usr/bin/env python3
"""
RISC-V 汇编执行验证器 - Docker版本
使用Docker运行RISC-V交叉编译和QEMU执行

用法:
    python docker_riscv_test.py
"""

import json
import subprocess
import tempfile
import os
import sys
import re
from pathlib import Path
import shutil

def check_docker():
    """检查Docker是否可用"""
    result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ Docker未安装或未运行")
        return False
    print(f"✅ Docker已安装: {result.stdout.strip()}")
    return True

def run_in_docker(asm_code, timeout=30):
    """
    使用Docker容器编译和运行RISC-V汇编
    返回: (exit_code, stdout, stderr)
    """
    container_name = 'jncc-riscv-test'

    # 清理旧容器
    subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True)

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        asm_file = Path(tmpdir) / 'test.s'
        exe_file = Path(tmpdir) / 'test'

        asm_file.write_text(asm_code)

        # Docker命令：在容器中编译并提取可执行文件
        compile_cmd = [
            'docker', 'run', '--rm',
            '--name', container_name,
            '-v', f'{tmpdir}:/work',
            '-w', '/work',
            'xicrobench/riscv-compiler:latest',
            'bash', '-c',
            f'gcc -o test test.s && cat test'
        ]

        try:
            compile_result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if compile_result.returncode != 0:
                return None, None, f"编译失败: {compile_result.stderr}"

            # 将编译出的ELF保存到临时文件
            with open(exe_file, 'wb') as f:
                f.write(compile_result.stdout.encode('latin-1'))

            # 用QEMU运行
            run_cmd = [
                'docker', 'run', '--rm',
                '--name', container_name,
                '-v', f'{tmpdir}:/work',
                '-w', '/work',
                'xicrobench/riscv-compiler:latest',
                'qemu-riscv64', './test'
            ]

            run_result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return run_result.returncode, run_result.stdout, run_result.stderr

        except subprocess.TimeoutExpired:
            return None, None, "执行超时"
        except Exception as e:
            return None, None, str(e)

def extract_return_value(asm_code):
    """从汇编代码提取预期返回值"""
    pattern = r'li\s+a0,\s*(-?\d+)'
    matches = re.findall(pattern, asm_code)
    if matches:
        # 找.L_exit_main之前最近的li a0
        lines = asm_code.split('\n')
        for i, line in enumerate(lines):
            if '.L_exit_main' in line:
                for j in range(i-1, -1, -1):
                    match = re.search(pattern, lines[j])
                    if match:
                        return int(match.group(1))
        # 如果没找到.L_exit_main，用最后一个
        return int(matches[-1])
    return None

def main():
    print("=" * 70)
    print("JNCC AI编译器 - Docker RISC-V 执行验证")
    print("=" * 70)

    if not check_docker():
        print("\n请安装Docker: https://docs.docker.com/get-docker/")
        print("或使用Linux系统直接安装: sudo apt install gcc-riscv64-linux-gnu qemu-user")
        sys.exit(1)

    # 检查是否有RISC-V编译器镜像
    print("\n检查RISC-V编译环境...")
    result = subprocess.run(
        ['docker', 'images', 'xicrobench/riscv-compiler'],
        capture_output=True,
        text=True
    )

    if 'xicrobench/riscv-compiler' not in result.stdout:
        print("正在拉取RISC-V编译环境镜像 (首次需要几分钟)...")
        pull_result = subprocess.run(
            ['docker', 'pull', 'xicrobench/riscv-compiler:latest'],
            capture_output=True,
            text=True
        )
        if pull_result.returncode != 0:
            print("❌ 镜像拉取失败")
            print("请手动运行: docker pull xicrobench/riscv-compiler:latest")
            sys.exit(1)
        print("✅ 镜像拉取完成")

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

    for i, tc in enumerate(test_cases[:5]):  # 只测5个
        tc_id = tc['id']
        xc_code = tc['xc_source'].replace('\n', ' ')[:50]
        oracle_asm = tc['asm_riscv64']

        print(f"\n【{i+1}/{min(5, len(test_cases))}】 {tc_id}")
        print(f"  XC: {xc_code}...")

        expected = extract_return_value(oracle_asm)
        print(f"  预期返回值: {expected}")

        # 执行Oracle汇编
        print(f"  执行Oracle汇编...")
        actual, stdout, stderr = run_in_docker(oracle_asm)

        if actual is None:
            print(f"  ⚠️ 执行失败: {stderr}")
            errors += 1
            results.append({'id': tc_id, 'status': 'error', 'expected': expected, 'actual': None})
            continue

        print(f"  实际返回值: {actual}")

        if actual == expected:
            print(f"  ✅ 通过")
            passed += 1
            status = 'pass'
        else:
            print(f"  ❌ 失败 (预期={expected}, 实际={actual})")
            failed += 1
            status = 'fail'

        results.append({
            'id': tc_id,
            'status': status,
            'expected': expected,
            'actual': actual
        })

    # 汇总
    total = passed + failed + errors
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)
    print(f"总测试数: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    print(f"错误: {errors} ⚠️")
    if total > 0:
        print(f"通过率: {passed/total*100:.1f}%")

    # 保存结果
    result_file = 'reports/docker_exec_results.json'
    os.makedirs('reports', exist_ok=True)
    with open(result_file, 'w') as f:
        json.dump({
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A"
            },
            'details': results
        }, f, indent=2)

    print(f"\n结果已保存到: {result_file}")

if __name__ == '__main__':
    main()
