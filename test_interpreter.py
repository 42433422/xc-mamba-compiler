#!/usr/bin/env python3
"""
XC代码解释器 - 修复版
用于验证XC代码的逻辑返回值
"""

import re
import json

def interpret_xc(xc_code):
    """简单XC解释器"""
    # 清理代码
    code = xc_code.replace('\n', ' ').replace('\t', ' ')

    # 变量存储
    vars = {}

    # 移除注释 (# ... } 之间的内容)
    code = re.sub(r'#\s*\{[^}]*\}', '', code)  # 移除 # { ... } 整体（如果只有入口）
    code = code.strip()

    # 提取变量赋值
    # 支持: $x = 5, $x: int = 5, $x = y + 3
    pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*int)?\s*=\s*([^;{}]+?)(?:;|\n|$)'
    matches = re.findall(pattern, code)

    for name, value_expr in matches:
        value_expr = value_expr.strip()
        # 尝试直接解析为数字
        try:
            vars[name] = int(value_expr)
        except:
            # 尝试计算表达式
            try:
                vars[name] = evaluate_simple(value_expr, vars)
            except:
                pass

    # 找return语句
    # 移除 # { 和 } 之间的内容
    code_inside = re.search(r'#\s*\{\s*(.*?)\s*\}', code, re.DOTALL)
    if code_inside:
        inside = code_inside.group(1)
    else:
        inside = code

    # 找最后一个 ^ xxx
    return_matches = re.findall(r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s*(?:;|\n|$|\}))', inside)
    if return_matches:
        final_return = return_matches[-1].strip()
        try:
            return evaluate_simple(final_return, vars)
        except:
            return 0

    return 0

def evaluate_simple(expr, vars):
    """计算简单表达式"""
    expr = expr.strip().replace(' ', '')

    if not expr:
        return 0

    # 纯数字
    try:
        return int(expr)
    except:
        pass

    # 变量
    if expr in vars:
        return vars[expr]

    # 括号表达式
    while '(' in expr:
        match = re.search(r'\(([^()]+)\)', expr)
        if not match:
            break
        inner = match.group(1).strip()
        result = calc_no_paren(inner, vars)
        expr = expr[:match.start()] + str(result) + expr[match.end():]

    return calc_no_paren(expr, vars)

def calc_no_paren(expr, vars):
    """计算无括号的表达式"""
    expr = expr.strip().replace(' ', '')

    # 处理乘除
    ops = re.split(r'(?=[+-])', expr)
    result = 0
    for op_expr in ops:
        op_expr = op_expr.strip()
        if not op_expr:
            continue

        # 检查是否有乘除
        md_match = re.match(r'^(.+?)([*/])(.+)$', op_expr)
        if md_match:
            left = md_match.group(1)
            op = md_match.group(2)
            right = md_match.group(3)

            l = vars.get(left, int(left) if left.isdigit() else 0)
            r = vars.get(right, int(right) if right.isdigit() else 0)

            if op == '*':
                result += l * r
            else:
                result += l // r if r != 0 else 0
        else:
            # 只有加减
            try:
                result += int(op_expr)
            except:
                try:
                    result += vars.get(op_expr, 0)
                except:
                    pass

    return result

def main():
    print("=" * 70)
    print("XC解释器测试")
    print("=" * 70)

    # 简单测试
    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x = 28 $y = 40 $z = x - y - 3 ^ z }", -15),
        ("# { $a = 5 $b = 21 $r = 0 ? (a > b) { $r = 1 } ?: { $r = 2 } ^ r }", 2),
    ]

    print("\n简单测试:")
    for code, expected in tests:
        result = interpret_xc(code)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{code[:40]}...' = {result} (expected {expected})")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
