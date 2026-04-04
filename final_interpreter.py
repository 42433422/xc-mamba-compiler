#!/usr/bin/env python3
"""
正确解析XC代码
"""

import re

def parse_xc(xc_code):
    """解析XC代码"""
    # 清理
    code = xc_code.replace('\n', ' ').replace('\t', ' ')
    code = re.sub(r'#\s*\{', '', code)
    code = re.sub(r'\}', '', code)

    vars = {}
    return_value = 0

    # 找返回语句
    return_match = re.search(r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s*$|\s*$)', code)
    if return_match:
        return_expr = return_match.group(1).strip()
        return_value = evaluate_expr(return_expr, vars)
        code_before_return = code[:return_match.start()]
    else:
        code_before_return = code

    # 找所有赋值语句 - 修复正则
    # $var = expr 或 $var: int = expr
    # expr可能包含变量、加减乘除、括号

    # 逐个找$开头的赋值
    while '$' in code_before_return:
        match = re.search(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*\$|\s*$)', code_before_return)
        if not match:
            match = re.search(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([0-9a-z_+\-*\/\(\)]+?)(?=\s*\$|\s*$)', code_before_return)

        if not match:
            break

        var_name = match.group(1)
        expr = match.group(2).strip()
        value = evaluate_expr(expr, vars)
        vars[var_name] = value
        print(f"DEBUG: ${var_name} = '{expr}' = {value}")

        code_before_return = code_before_return[match.end():]

    return return_value

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

    # 括号
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

    # 乘除
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
    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }", -15),
        ("# { $a = 5 $b = 21 $r = 0 ? (a > b) { $r = 1 } ?: { $r = 2 } ^ r }", 2),
    ]

    print("=" * 60)
    print("XC代码解析测试")
    print("=" * 60)

    for code, expected in tests:
        print(f"\n解析: {code}")
        result = parse_xc(code)
        status = "✅" if result == expected else "❌"
        print(f"{status} Result: {result}, Expected: {expected}")

if __name__ == '__main__':
    main()
