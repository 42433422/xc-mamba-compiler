#!/usr/bin/env python3
"""
调试simple_interpreter
"""

import re

code = "# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }"

# 清理
code = re.sub(r'#\s*\{', ' ', code)
code = re.sub(r'\}', ' ', code)
code = re.sub(r'\n', ' ', code)
code = re.sub(r'\t', ' ', code)
print(f"清理后: '{code}'")

# 找赋值
vars = {}
assign_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*\$|\s*$)'
matches = list(re.finditer(assign_pattern, code))
print(f"找到 {len(matches)} 个赋值")

for m in matches:
    var_name = m.group(1)
    expr = m.group(2).strip()
    print(f"  ${var_name} = '{expr}'")

    # 计算表达式
    for var, val in vars.items():
        expr = expr.replace(var, str(val))
    print(f"    替换后: '{expr}'")

    try:
        val = eval(expr)
        vars[var_name] = val
        print(f"    = {val}")
    except Exception as e:
        print(f"    计算失败: {e}")
