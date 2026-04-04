#!/usr/bin/env python3
"""
分析第一个测试用例的返回值问题
"""

import re
import json

# 读取第一个测试用例
with open('dataset/xc_asm_test.jsonl') as f:
    tc = json.loads(f.readline())

xc_code = tc['xc_source']
asm = tc['asm_riscv64']

print("XC代码:")
print(xc_code)
print()

print("汇编关键部分:")
lines = asm.split('\n')
for i, line in enumerate(lines):
    if '16(s0)' in line or '.L_exit' in line or 'li a0' in line or 'lw a0' in line or 'ret' in line:
        print(f"{i:3}: {line}")

print()
print("问题分析:")
print("=" * 60)
print("""
执行流程:
1. $z = x - y - 3 = 28 - 40 - 3 = -15
2. sw a0, 16(s0)    # 把z=-15存入内存
3. lw a0, 16(s0)    # 加载z=-15到a0
4. j .L_exit_main   # 跳转跳过下一条
5. li a0, 0         # 被跳转，跳过！
6. .L_exit_main:
7. ret             # 返回a0=-15

所以返回值应该是 -15，不是 0 或 3！

我的extract_asm_return函数有bug：它从后往前找'li a0'
但实际上'li a0, 0'被跳转跳过了！
""")
