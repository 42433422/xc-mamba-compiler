#!/usr/bin/env python3
"""
调试第二个测试
"""

import re

code = "# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }"

# 清理
code = re.sub(r'#\s*\{', '', code)
code = re.sub(r'\}', '', code)

print(f"清理后: '{code}'")

# 按换行分割
lines = code.split('\n')
print(f"行数: {len(lines)}")
for i, line in enumerate(lines):
    print(f"Line {i}: '{line}'")
