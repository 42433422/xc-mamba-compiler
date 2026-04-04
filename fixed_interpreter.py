#!/usr/bin/env python3
"""
正确解析XC代码
"""

import re
import json

def tokenize_xc(code):
    """将XC代码分词"""
    # 移除 # { 和 } 这些标记
    code = re.sub(r'#\s*\{', '', code)
    code = re.sub(r'\}', '', code)

    # 分行
    lines = code.split('\n')
    tokens = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 分割成token
        # 处理 $var: int = expr 格式
        if line.startswith('$'):
            # 变量声明
            match = re.match(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*(.+)', line)
            if match:
                var_name = match.group(1)
                expr = match.group(2).strip()
                tokens.append(('VAR', var_name, expr))
                continue

        if line.startswith('^'):
            # 返回语句
            expr = line[1:].strip()
            tokens.append(('RETURN', expr))
            continue

        tokens.append(('STMT', line))

    return tokens

def evaluate_expr(expr, vars):
    """计算表达式"""
    expr = expr.strip()

    # 纯数字
    try:
        return int(expr)
    except:
        pass

    # 纯变量
    if expr in vars:
        return vars[expr]

    # 解析加减乘除
    # 先处理加减（从左到右）
    expr = expr.replace(' ', '')

    # 分割成token
    tokens = []
    current = ''
    for c in expr:
        if c in '+-*/()':
            if current:
                tokens.append(current)
                current = ''
            tokens.append(c)
        else:
            current += c
    if current:
        tokens.append(current)

    # 计算
    # 简单实现：只处理加减乘除，没有优先级
    # 实际应该用栈实现

    # 先处理乘除
    i = 0
    while i < len(tokens):
        if tokens[i] == '*':
            left = vars.get(tokens[i-1], int(tokens[i-1]) if tokens[i-1].lstrip('-').isdigit() else 0)
            right = vars.get(tokens[i+1], int(tokens[i+1]) if tokens[i+1].lstrip('-').isdigit() else 0)
            result = left * right
            tokens = tokens[:i-1] + [str(result)] + tokens[i+2:]
            i = 0
        elif tokens[i] == '/':
            left = vars.get(tokens[i-1], int(tokens[i-1]) if tokens[i-1].lstrip('-').isdigit() else 0)
            right = vars.get(tokens[i+1], int(tokens[i+1]) if tokens[i+1].lstrip('-').isdigit() else 0)
            result = left // right if right != 0 else 0
            tokens = tokens[:i-1] + [str(result)] + tokens[i+2:]
            i = 0
        i += 1

    # 处理加减
    result = 0
    current_op = '+'
    for token in tokens:
        if token == '+':
            current_op = '+'
        elif token == '-':
            current_op = '-'
        elif token in '*/':
            pass  # 已处理
        else:
            try:
                val = int(token)
            except:
                val = vars.get(token, 0)
            if current_op == '+':
                result += val
            else:
                result -= val

    return result

def interpret_xc(xc_code):
    """解释XC代码，返回退出码"""
    tokens = tokenize_xc(xc_code)
    vars = {}

    return_value = 0

    for token_type, *rest in tokens:
        if token_type == 'VAR':
            var_name, expr = rest
            value = evaluate_expr(expr, vars)
            vars[var_name] = value

        elif token_type == 'RETURN':
            expr = rest[0]
            return_value = evaluate_expr(expr, vars)

    return return_value

def main():
    print("=" * 60)
    print("XC代码解析测试")
    print("=" * 60)

    # 测试用例
    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }", -15),
        ("# { $a = 5 $b = 21 $r = 0 ? (a > b) { $r = 1 } ?: { $r = 2 } ^ r }", 2),
    ]

    for code, expected in tests:
        result = interpret_xc(code)
        status = "✅" if result == expected else "❌"
        print(f"{status} {result} (expected {expected})")
        print(f"   Code: {code[:50]}...")
        print()

if __name__ == '__main__':
    main()
