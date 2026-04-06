#!/usr/bin/env python3
"""
正确解析XC代码 - 修复版
"""

import re
import json

def parse_xc(xc_code):
    """解析XC代码"""
    # 移除 # { 和 }
    code = xc_code.replace('\n', ' ').replace('\t', ' ')
    code = re.sub(r'#\s*\{', '', code)
    code = re.sub(r'\}', '', code)

    vars = {}
    return_value = 0

    # 分割成语句 (按 ; 或 ^ 分隔)
    # 先处理赋值语句
    lines = code.split(';')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否是返回语句
        if line.startswith('^'):
            # 返回语句
            expr = line[1:].strip()
            return_value = evaluate_expr(expr, vars)
            continue

        # 赋值语句 $var = expr 或 $var: int = expr
        if line.startswith('$'):
            # 匹配 $var = expr 或 $var: int = expr
            match = re.match(r'\$([a-zA-Z_][a-zA-Z0-9_]*)(?::\s*int)?\s*=\s*(.+)', line)
            if match:
                var_name = match.group(1)
                expr = match.group(2).strip()
                value = evaluate_expr(expr, vars)
                vars[var_name] = value

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

    # 移除空格
    expr = expr.replace(' ', '')

    # 处理括号内的表达式
    while '(' in expr:
        match = re.search(r'\(([^()]+)\)', expr)
        if not match:
            break
        inner = match.group(1)
        result = calc_expr(inner, vars)
        expr = expr[:match.start()] + str(result) + expr[match.end():]

    # 计算无括号的表达式
    return calc_expr(expr, vars)

def calc_expr(expr, vars):
    """计算简单表达式（无括号）"""
    if not expr:
        return 0

    # 移除空格
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
    # 分割加减
    parts = re.split(r'(?=[+-])', expr)
    result = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 检查是否有乘除
        if '*' in part or '/' in part:
            # 分割乘除
            md_parts = re.split(r'([*/])', part)
            first = True
            md_result = 0
            md_op = '*'

            for p in md_parts:
                p = p.strip()
                if not p:
                    continue

                if p == '*':
                    md_op = '*'
                elif p == '/':
                    md_op = '/'
                else:
                    try:
                        val = int(p)
                    except:
                        val = vars.get(p, 0)

                    if first:
                        md_result = val
                        first = False
                    elif md_op == '*':
                        md_result *= val
                    elif md_op == '/':
                        md_result = md_result // val if val != 0 else 0

            result += md_result
        else:
            # 只有加减
            try:
                result += int(part)
            except:
                result += vars.get(part, 0)

    return result

def main():
    print("=" * 60)
    print("XC代码解析测试")
    print("=" * 60)

    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }", -15),
        ("# { $a = 5 $b = 21 $r = 0 ? (a > b) { $r = 1 } ?: { $r = 2 } ^ r }", 2),
    ]

    for code, expected in tests:
        result = parse_xc(code)
        status = "✅" if result == expected else "❌"
        print(f"{status} Result: {result}, Expected: {expected}")
        print(f"   Code: {code}")
        print()

if __name__ == '__main__':
    main()
