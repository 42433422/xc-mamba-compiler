#!/usr/bin/env python3
"""
正确解析XC代码 - 处理 ^ 作为语句分隔符
"""

import re
import json

def parse_xc(xc_code):
    """解析XC代码"""
    # 清理
    code = xc_code.replace('\n', ' ').replace('\t', ' ')
    code = re.sub(r'#\s*\{', '', code)
    code = re.sub(r'\}', '', code)

    vars = {}
    return_value = 0

    # 按行分割
    lines = code.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 如果行中有 ^ 符号（不是开头），需要分割
        if ' ^ ' in line or line.startswith('^'):
            # 这是返回语句
            if '^' in line:
                parts = line.split('^')
                # ^ 之前可能是赋值语句
                before_caret = parts[0].strip()
                if before_caret and before_caret.startswith('$'):
                    # 处理赋值
                    match = re.match(r'\$([a-zA-Z_][a-zA-Z0-9_]*)(?::\s*int)?\s*=\s*(.+)', before_caret)
                    if match:
                        var_name = match.group(1)
                        expr = match.group(2).strip()
                        value = evaluate_expr(expr, vars)
                        vars[var_name] = value

                # ^ 之后是返回表达式
                after_caret = parts[-1].strip()
                if after_caret:
                    return_value = evaluate_expr(after_caret, vars)
        else:
            # 普通赋值语句
            if line.startswith('$'):
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
    """计算表达式"""
    if not expr:
        return 0
    expr = expr.replace(' ', '')

    try:
        return int(expr)
    except:
        pass

    if expr in vars:
        return vars[expr]

    # 处理乘除
    parts = re.split(r'(?=[+-])', expr)
    result = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if '*' in part or '/' in part:
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
    ]

    for code, expected in tests:
        print(f"\n解析: {code}")
        result = parse_xc(code)
        status = "✅" if result == expected else "❌"
        print(f"{status} Result: {result}, Expected: {expected}")

if __name__ == '__main__':
    main()
