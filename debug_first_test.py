"""
详细分析第一个测试用例的返回值问题
"""

import json

# 读取第一个测试用例
with open('dataset/xc_asm_test.jsonl') as f:
    tc = json.loads(f.readline())

print("=" * 70)
print("详细分析: xcasm_122_12345")
print("=" * 70)

print("\n【XC代码】")
print(tc['xc_source'])

print("\n【C参考代码】")
print(tc['c_reference'])

print("\n【RISC-V汇编（关键部分）】")
asm_lines = tc['asm_riscv64'].split('\n')
for i, line in enumerate(asm_lines):
    if '16(s0)' in line or '.L_exit' in line or 'ret' in line:
        print(f"  {i}: {line}")

print("\n" + "=" * 70)
print("【手动计算XC逻辑】")
print("=" * 70)
print("x = 28")
print("y = 40")
print("z = x - y - 3")
print("z = 28 - 40 - 3")
print("z = -15")
print("\n所以 return z 应该返回 -15")

print("\n" + "=" * 70)
print("【问题分析】")
print("=" * 70)
print("汇编中:")
print("  lw a0, 16(s0)  # 加载z的值到a0，此时a0=-15")
print("  j .L_exit_main  # 跳转跳过下一条指令")
print("  li a0, 0        # 这行被跳过，不会执行")
print("")
print("但我的脚本提取到最终a0=0，这是错误的！")
print("因为跳转指令j会跳过 li a0, 0")
print("")
print("实际执行流程会返回 -15，不是 0")

print("\n" + "=" * 70)
print("【结论】")
print("=" * 70)
print("数据集和Oracle生成的汇编是正确的！")
print("我的验证脚本有bug，没有正确处理跳转指令")
print("")
print("正确的返回值应该是 -15 (通过 lw a0, 16(s0) 获得)")
