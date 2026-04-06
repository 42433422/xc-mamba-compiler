#!/usr/bin/env python3
"""
调试正则
"""

import re

code = "$x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z"

print(f"代码: '{code}'")

# 找返回语句
return_pattern = r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s*$|\s+)'
return_match = re.search(return_pattern, code)
if return_match:
    print(f"找到返回: '{return_match.group(1)}'")
    print(f"返回前: '{code[:return_match.start()]}'")
else:
    print("没找到返回语句")

# 找赋值语句
assign_pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)(?::\s*int)?\s*=\s*([0-9a-z_+\-*\/\(\)\s]+?)(?=\s*\$|\s*$)'
matches = re.findall(assign_pattern, code)
print(f"\n赋值语句: {len(matches)} 个")
for m in matches:
    print(f"  {m}")
