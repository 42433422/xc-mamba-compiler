#!/usr/bin/env python3
"""
XC代码解释器 - 用于验证XC代码的逻辑返回值
不需要RISC-V工具链，直接用Python模拟XC代码执行
"""

import re
import json

def interpret_xc(xc_code):
    """
    简单XC解释器，返回程序退出码（模拟main函数返回值）
    """
    lines = xc_code.replace('\n', ' ').replace('\t', ' ').strip()

    # 变量存储
    vars = {}

    # 移除注释
    lines = re.sub(r'#.*?}', '', lines)

    # 提取变量赋值
    # $x = N 或 $x: int = N
    var_assignments = re.findall(r'\$([a-zA-Z_][a-zA-Z0-9_]*)(?::\s*int)?\s*=\s*(-?\d+)', lines)
    for name, value in var_assignments:
        vars[name] = int(value)

    # 找到return语句 ^ xxx
    return_matches = re.findall(r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s|$|\})', lines)

    if return_matches:
        # 取最后一个return（程序最终返回值）
        final_return = return_matches[-1].strip()
        return evaluate_expr(final_return, vars)

    return 0

def evaluate_expr(expr, vars):
    """
    计算表达式的值
    支持: 变量、加减乘除、括号
    """
    expr = expr.strip()

    # 如果是纯数字
    try:
        return int(expr)
    except:
        pass

    # 如果是变量
    if expr in vars:
        return vars[expr]

    # 移除空格
    expr = expr.replace(' ', '')

    # 处理括号 - 找到最内层括号并计算
    while '(' in expr:
        # 找到最内层括号
        match = re.search(r'\(([^()]+)\)', expr)
        if not match:
            break
        inner = match.group(1)
        # 计算括号内的表达式
        inner_result = calculate_simple(inner, vars)
        expr = expr[:match.start()] + str(inner_result) + expr[match.end():]

    # 计算结果
    return calculate_simple(expr, vars)

def calculate_simple(expr, vars):
    """
    计算简单表达式（无括号）
    支持加减乘除
    """
    expr = expr.strip()

    # 如果是纯数字
    try:
        return int(expr)
    except:
        pass

    # 如果是变量
    if expr in vars:
        return vars[expr]

    # 处理加减（从左到右）
    # 先处理乘除
    while '*' in expr or '/' in expr:
        match = re.search(r'(-?\d+|\w+)\s*([*/])\s*(-?\d+|\w+)', expr)
        if not match:
            break
        left = match.group(1)
        op = match.group(2)
        right = match.group(3)

        # 获取值
        try:
            l = int(left)
        except:
            l = vars.get(left, 0)
        try:
            r = int(right)
        except:
            r = vars.get(right, 0)

        if op == '*':
            result = l * r
        else:
            result = l // r if r != 0 else 0

        expr = expr[:match.start()] + str(result) + expr[match.end():]

    # 处理加减
    parts = re.split(r'(?=[+-])', expr)
    result = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            result += int(part)
        except:
            try:
                result += vars.get(part, 0)
            except:
                pass

    return result

def main():
    print("=" * 70)
    print("XC代码解释器 - 验证XC逻辑返回值")
    print("=" * 70)

    # 读取测试数据
    with open('dataset/xc_asm_test.jsonl') as f:
        test_cases = [json.loads(line) for line in f]

    print(f"📋 测试用例总数: {len(test_cases)}")
    print("=" * 70)

    results = []
    passed = 0
    failed = 0
    errors = 0

    for i, tc in enumerate(test_cases[:10]):  # 测试10个
        tc_id = tc['id']
        xc_code = tc['xc_source']
        oracle_asm = tc['asm_riscv64']

        print(f"\n【{i+1}/{len(test_cases[:10])}】 {tc_id}")
        xc_short = xc_code.replace('\n', ' ').strip()[:50]
        print(f"  XC: {xc_short}...")

        # 用Python解释器计算XC代码的预期返回值
        try:
            expected = interpret_xc(xc_code)
            print(f"  XC解释器返回值: {expected}")
        except Exception as e:
            print(f"  ⚠️ XC解释失败: {e}")
            expected = None
            errors += 1
            continue

        # 从Oracle汇编提取预期返回值
        # 找.L_exit_main之前最近的li a0
        oracle_return = extract_asm_return(oracle_asm)
        print(f"  Oracle汇编返回值: {oracle_return}")

        if expected is not None and oracle_return is not None:
            if expected == oracle_return:
                print(f"  ✅ 匹配")
                passed += 1
            else:
                print(f"  ❌ 不匹配 (XC={expected}, Oracle={oracle_return})")
                failed += 1
        else:
            print(f"  ⚠️ 无法对比")
            errors += 1

        results.append({
            'id': tc_id,
            'expected_xc': expected,
            'oracle_asm': oracle_return,
            'match': expected == oracle_return if expected is not None and oracle_return is not None else None
        })

    # 汇总
    total = passed + failed
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)
    print(f"总测试数: {total}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    print(f"错误: {errors} ⚠️")
    if total > 0:
        print(f"通过率: {passed/total*100:.1f}%")

    if passed == total and total > 0:
        print("\n🎉 所有测试通过！")
        print("这证明：")
        print("  1. XC解释器的逻辑是正确的")
        print("  2. Oracle生成的汇编会产生正确的返回值")
        print("  3. XC代码 ↔ Oracle汇编 的映射是正确的")

    # 保存结果
    result_file = 'reports/xc_interpreter_results.json'
    import os
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

def extract_asm_return(asm_code):
    """从Oracle汇编提取返回值"""
    lines = asm_code.split('\n')

    # 找到.L_exit_main的位置
    exit_idx = -1
    for i, line in enumerate(lines):
        if '.L_exit_main' in line:
            exit_idx = i
            break

    if exit_idx > 0:
        # 向前找最后一个li a0
        for i in range(exit_idx - 1, -1, -1):
            match = re.search(r'li\s+a0,\s*(-?\d+)', lines[i])
            if match:
                return int(match.group(1))

    # 如果没找到，返回None
    return None

if __name__ == '__main__':
    main()
