import json
import re
import sys

# 读取测试数据
with open('dataset/xc_asm_test.jsonl') as f:
    test_cases = [json.loads(line) for line in f]

print(f"测试用例总数: {len(test_cases)}")
print("=" * 60)

# 统计测试用例的特征
features = {}
for tc in test_cases:
    for f in tc.get('feature_tags', []):
        features[f] = features.get(f, 0) + 1

print("语法特征分布:")
for f, count in features.items():
    print(f"  {f}: {count}")

print("=" * 60)

# 显示几个示例
for i, tc in enumerate(test_cases[:3]):
    print(f"\n【测试用例 {i+1}】")
    print(f"ID: {tc['id']}")
    xc = tc['xc_source'].replace('\n', ' ')[:80]
    print(f"XC: {xc}...")

    # 提取预期返回值
    c_ref = tc.get('c_reference', '')
    matches = re.findall(r'return (\d+)', c_ref)
    if matches:
        print(f"预期返回值: {matches}")

    asm = tc['asm_riscv64'][:100].replace('\t', ' ')
    print(f"Oracle汇编: {asm}...")

print("\n" + "=" * 60)
print("由于Windows环境没有RISC-V交叉编译工具链(qemu-riscv64),")
print("无法直接执行验证。但可以通过对比AI生成和Oracle生成的")
print("汇编代码结构来评估质量。")
