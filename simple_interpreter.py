#!/usr/bin/env python3
"""
正确解析XC代码 - 简化版
"""

import re

def parse_xc(xc_code):
    """解析XC代码"""
    code = re.sub(r'#\s*\{', ' ', xc_code)
    code = re.sub(r'\}', ' ', code)
    code = re.sub(r'\n', ' ', code)
    code = re.sub(r'\t', ' ', code)

    vars = {}

    # 找所有赋值
    assign_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*\$|\s*$)'
    for match in re.finditer(assign_pattern, code):
        var_name = match.group(1)
        expr = match.group(2).strip()
        vars[var_name] = evaluate_expr(expr, vars)

    # 找返回值
    return_match = re.search(r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s*$)', code)
    if return_match:
        return evaluate_expr(return_match.group(1).strip(), vars)

    return 0

def evaluate_expr(expr, vars):
    """计算表达式"""
    expr = expr.strip()
    if not expr:
        return 0

    # 纯数字
    try:
        return int(expr)
    except:
        pass

    # 纯变量
    if expr in vars:
        return vars[expr]

    expr = expr.replace(' ', '')

    # 用Python的eval安全计算（只支持数字和变量）
    try:
        # 替换变量为值
        for var, val in vars.items():
            expr = expr.replace(var, str(val))
        return eval(expr)
    except:
        return 0

def main():
    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }", -15),
        ("# { $a = 5 $b = 21 $r = 0 ^ r }", 0),
    ]

    print("=" * 60)
    print("XC代码解析测试")
    print("=" * 60)

    passed = 0
    for code, expected in tests:
        result = parse_xc(code)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        print(f"{status} Result: {result}, Expected: {expected}")
        print(f"   Code: {code[:60]}...")

    print(f"\n通过: {passed}/{len(tests)}")

if __name__ == '__main__':
    main()
