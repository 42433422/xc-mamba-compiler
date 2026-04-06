#!/usr/bin/env python3
"""
正确解析XC代码 - 逐字符解析版
"""

import re

def parse_xc(xc_code):
    """解析XC代码"""
    # 清理
    code = re.sub(r'#\s*\{', ' ', xc_code)
    code = re.sub(r'\}', ' ', code)
    code = re.sub(r'\n', ' ', code)
    code = re.sub(r'\t', ' ', code)

    vars = {}

    # 用更简单的方式：先按 $ 分隔
    parts = code.split('$')
    print(f"DEBUG: 分割${len(parts)}部分")

    for i, part in enumerate(parts):
        if i == 0:  # 跳过第一个空部分
            continue

        part = part.strip()
        print(f"DEBUG part {i}: '{part}'")

        # 匹配 $var: int = expr 或 $var = expr
        # expr可能包含 ^ (返回语句)
        match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*(.+)', part)
        if not match:
            match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)', part)

        if match:
            var_name = match.group(1)
            rest = match.group(2).strip()
            print(f"  -> var={var_name}, rest='{rest}'")

            # 检查是否有返回语句 ^
            if ' ^ ' in rest or rest.startswith('^'):
                # 分割赋值和返回
                if ' ^ ' in rest:
                    assign_part, return_part = rest.split(' ^ ', 1)
                    assign_part = assign_part.strip()
                    return_part = return_part.strip()

                    if assign_part:
                        value = evaluate_expr(assign_part, vars)
                        vars[var_name] = value
                        print(f"  -> 赋值 ${var_name} = {value}")

                    if return_part:
                        return_value = evaluate_expr(return_part, vars)
                        print(f"  -> 返回 ^{return_part} = {return_value}")
                        return return_value
                elif rest.startswith('^'):
                    # 整个都是返回语句
                    return_part = rest[1:].strip()
                    return_value = evaluate_expr(return_part, vars)
                    print(f"  -> 返回 ^{return_part} = {return_value}")
                    return return_value
            else:
                # 只有赋值
                value = evaluate_expr(rest, vars)
                vars[var_name] = value
                print(f"  -> 赋值 ${var_name} = {value}")

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
    tests = [
        ("# { $x = 10 ^ x }", 10),
        ("# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }", -15),
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
