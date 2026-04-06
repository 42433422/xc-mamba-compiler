#!/usr/bin/env python3
"""
调试XC解析问题
"""

import re

# 测试用例1
xc_code = """# {
    $x: int = 28
    $y: int = 40
    $z: int = x - y - 3
    ^ z
}"""

print("原始XC代码:")
print(repr(xc_code))
print()

# 移除换行和多余空格
code = xc_code.replace('\n', ' ').replace('\t', ' ')
print("清理后:")
print(repr(code))
print()

# 尝试提取变量赋值
print("尝试提取变量赋值:")
print("=" * 50)

# 方法1: 我的原始正则
pattern1 = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*int)?\s*=\s*([^;{}]+?)(?:;|\n|$)'
matches1 = re.findall(pattern1, code)
print(f"方法1: {len(matches1)} 个匹配")
for m in matches1:
    print(f"  {m}")

print()

# 方法2: 改进的正则
pattern2 = r'\$([a-zA-Z_][a-zA-Z0-9_]*)(?::\s*int)?\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*(?:;|$|\}))'
matches2 = re.findall(pattern2, code)
print(f"方法2: {len(matches2)} 个匹配")
for m in matches2:
    print(f"  {m}")

print()

# 尝试找return
print("尝试找return:")
print("=" * 50)
return_pattern = r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s*(?:;|\n|$|\}))'
returns = re.findall(return_pattern, code)
print(f"找到 {len(returns)} 个return")
for r in returns:
    print(f"  '{r}'")

print()

# 完整解析
print("完整解析:")
print("=" * 50)

def parse_xc_simple(code):
    vars = {}

    # 提取变量 $x = N 或 $x: int = N
    # 匹配模式: $变量名: int = 值
    var_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*(?:;|\}|\n|$))'

    for match in re.finditer(var_pattern, code):
        name = match.group(1)
        value_str = match.group(2).strip()
        print(f"找到变量赋值: ${name} = '{value_str}'")

        # 尝试计算值
        # 先尝试直接转数字
        try:
            value = int(value_str)
            vars[name] = value
            print(f"  直接值: {value}")
        except:
            # 尝试解析表达式
            # 先看看能不能找到已知的变量
            print(f"  需要计算表达式...")

    return vars

vars = parse_xc_simple(code)
print(f"\n解析出的变量: {vars}")
