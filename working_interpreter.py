#!/usr/bin/env python3
"""
正确解析XC代码 - 最终版
"""

import re
import json

def parse_xc(xc_code):
    """解析XC代码"""
    # 清理
    code = re.sub(r'#\s*\{', ' ', xc_code)
    code = re.sub(r'\}', ' ', code)
    code = re.sub(r'\n', ' ', code)
    code = re.sub(r'\t', ' ', code)

    vars = {}
    return_value = 0

    # 先收集所有返回语句
    return_match = re.search(r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s*$)', code)
    if return_match:
        return_expr = return_match.group(1).strip()

    # 找所有赋值语句
    assign_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*\$|\s*$)'
    for match in re.finditer(assign_pattern, code):
        var_name = match.group(1)
        expr = match.group(2).strip()
        value = evaluate_expr(expr, vars)
        vars[var_name] = value

    # 计算返回值
    if return_match:
        return_value = evaluate_expr(return_expr, vars)

    return return_value

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

    # 处理括号
    while '(' in expr:
        match = re.search(r'\(([^()]+)\)', expr)
        if not match:
            break
        inner = match.group(1)
        result = calc_expr(inner, vars)
        expr = expr[:match.start()] + str(result) + expr[match.end():]

    return calc_expr(expr, vars)

def calc_expr(expr, vars):
    """计算表达式，支持加减乘除和变量"""
    if not expr:
        return 0
    expr = expr.replace(' ', '')

    # 纯数字
    try:
        return int(expr)
    except:
        pass

    # 纯变量
    if expr in vars:
        return vars[expr]

    # 处理乘除（优先级高）
    # 找到所有乘除运算并先计算
    i = 0
    while i < len(expr):
        if expr[i] in '*/':
            # 找到操作符左边的数
            left_start = i - 1
            while left_start >= 0 and expr[left_start] in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_':
                left_start -= 1
            left_start += 1

            # 找到操作符右边的数
            right_end = i + 1
            while right_end < len(expr) and expr[right_end] in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_':
                right_end += 1

            left = expr[left_start:i]
            op = expr[i]
            right = expr[i+1:right_end]

            # 获取值
            try:
                l = int(left) if left in '0123456789' else vars.get(left, 0)
            except:
                l = vars.get(left, 0)
            try:
                r = int(right) if right in '0123456789' else vars.get(right, 0)
            except:
                r = vars.get(right, 0)

            if op == '*':
                result = l * r
            else:
                result = l // r if r != 0 else 0

            # 替换
            expr = expr[:left_start] + str(result) + expr[right_end:]
            i = -1

        i += 1

    # 处理加减（从左到右）
    i = 0
    negative = False
    result = 0
    current_num = ''

    for c in expr:
        if c == '-':
            if current_num:
                result += int(current_num) if not negative else -int(current_num)
                current_num = ''
            negative = True
        elif c == '+':
            if current_num:
                result += int(current_num) if not negative else -int(current_num)
                current_num = ''
            negative = False
        else:
            current_num += c

    if current_num:
        result += int(current_num) if not negative else -int(current_num)

    return result

def main():
    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }", -15),
        ("# { $a = 5 $b = 21 $r = 0 ? (a > b) { $r = 1 } ?: { $r = 2 } ^ r }", 2),
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
        print()

    print(f"通过: {passed}/{len(tests)}")

if __name__ == '__main__':
    main()
