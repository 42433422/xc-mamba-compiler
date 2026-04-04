#!/usr/bin/env python3
"""
调试XC解析
"""

import re

code = "# { $x = 10 ^ x }"

print(f"原始: {repr(code)}")

# 移除 # {
code = re.sub(r'#\s*\{', '', code)
print(f"移除#{{: {repr(code)}")

# 移除 }
code = re.sub(r'\}', '', code)
print(f"移除}}: {repr(code)}")

print(f"最终: {repr(code)}")

# 分行
lines = code.split('\n')
print(f"分行: {lines}")

for line in lines:
    line = line.strip()
    print(f"处理行: {repr(line)}")

    if line.startswith('$'):
        # 变量声明
        match = re.match(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*int\s*=\s*(.+)', line)
        if match:
            print(f"  匹配到: var={match.group(1)} expr={match.group(2)}")
        else:
            # 尝试无类型
            match2 = re.match(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)', line)
            if match2:
                print(f"  匹配到(无类型): var={match2.group(1)} expr={match2.group(2)}")
            else:
                print(f"  未匹配!")
