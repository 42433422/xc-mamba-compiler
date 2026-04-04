#!/usr/bin/env python3
"""
调试parse_xc
"""

import re

code = "# { $x = 10 ^ x }"

# 移除 # { 和 }
code = re.sub(r'#\s*\{', '', code)
code = re.sub(r'\}', '', code)
print(f"处理后: '{code}'")

# 按 ; 分割
parts = code.split(';')
print(f"按;分割: {parts}")

for i, part in enumerate(parts):
    part = part.strip()
    print(f"Part {i}: '{part}'")

    if not part:
        continue

    if part.startswith('^'):
        print(f"  -> 返回语句: {part[1:].strip()}")
    elif part.startswith('$'):
        print(f"  -> 赋值语句")
