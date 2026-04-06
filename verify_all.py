#!/usr/bin/env python3
"""
XC代码解释器 - 最终版
用于验证XC代码的逻辑返回值
"""

import re
import json

def parse_xc(xc_code):
    """解析XC代码"""
    code = re.sub(r'#\s*\{', ' ', xc_code)
    code = re.sub(r'\}', ' ', code)
    code = re.sub(r'\n', ' ', code)
    code = re.sub(r'\t', ' ', code)

    vars = {}

    parts = code.split('$')

    for i, part in enumerate(parts):
        if i == 0:
            continue

        part = part.strip()

        match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*(.+)', part)
        if not match:
            match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)', part)

        if match:
            var_name = match.group(1)
            rest = match.group(2).strip()

            if ' ^ ' in rest or rest.startswith('^'):
                if ' ^ ' in rest:
                    assign_part, return_part = rest.split(' ^ ', 1)
                    assign_part = assign_part.strip()
                    return_part = return_part.strip()

                    if assign_part:
                        value = evaluate_expr(assign_part, vars)
                        vars[var_name] = value

                    if return_part:
                        return evaluate_expr(return_part, vars)
                elif rest.startswith('^'):
                    return evaluate_expr(rest[1:].strip(), vars)
            else:
                value = evaluate_expr(rest, vars)
                vars[var_name] = value

    return 0

def evaluate_expr(expr, vars):
    """计算表达式"""
    expr = expr.strip()
    if not expr:
        return 0

    try:
        return int(expr)
    except:
        pass

    if expr in vars:
        return vars[expr]

    expr = expr.replace(' ', '')

    try:
        for var, val in vars.items():
            expr = expr.replace(var, str(val))
        return eval(expr)
    except:
        return 0

def main():
    with open('dataset/xc_asm_test.jsonl') as f:
        test_cases = [json.loads(line) for line in f]

    print("=" * 70)
    print("XC解释器验证")
    print("=" * 70)

    passed = 0
    failed = 0
    results = []

    for tc in test_cases[:10]:
        tc_id = tc['id']
        xc_code = tc['xc_source']
        oracle_asm = tc['asm_riscv64']

        xc_result = parse_xc(xc_code)
        asm_result = extract_asm_return(oracle_asm)

        print(f"\n[{tc_id}]")
        print(f"  XC解释器: {xc_result}")
        print(f"  Oracle汇编: {asm_result}")

        if xc_result == asm_result:
            print(f"  ✅ 匹配")
            passed += 1
        else:
            print(f"  ❌ 不匹配")
            failed += 1

        results.append({
            'id': tc_id,
            'xc_result': xc_result,
            'asm_result': asm_result,
            'match': xc_result == asm_result
        })

    print("\n" + "=" * 70)
    print(f"汇总: {passed}通过 / {failed}失败")
    print("=" * 70)

    if failed == 0:
        print("\n🎉 所有测试通过！XC解释器和Oracle汇编返回值一致！")

def extract_asm_return(asm_code):
    """从Oracle汇编提取返回值"""
    lines = asm_code.split('\n')

    for i, line in enumerate(lines):
        if '.L_exit_main' in line:
            for j in range(i - 1, -1, -1):
                match = re.search(r'li\s+a0,\s*(-?\d+)', lines[j])
                if match:
                    return int(match.group(1))

    return None

if __name__ == '__main__':
    main()
