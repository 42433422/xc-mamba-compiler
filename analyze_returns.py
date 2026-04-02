import json
import re

with open('dataset/xc_asm_test.jsonl') as f:
    test_cases = [json.loads(line) for line in f]

print("=" * 70)
print("JNCC AI编译器 - 真实预期返回值分析")
print("=" * 70)

for tc in test_cases[:5]:
    xc = tc['xc_source'].replace('\n', ' ')[:70]
    asm = tc['asm_riscv64']
    c_ref = tc.get('c_reference', '')

    returns = re.findall(r'return (\d+)', c_ref)
    if returns:
        expected_return = returns[-1]
    else:
        expected_return = "N/A"

    print(f"\n[{tc['id']}]")
    print(f"XC: {xc}...")
    print(f"C参考代码中的return值: {returns}")
    print(f"最终预期返回值: {expected_return}")

print("\n" + "=" * 70)
print("结论：需要通过实际执行RISC-V汇编来验证正确性")
print("Windows环境缺少riscv64工具链")
print("=" * 70)
