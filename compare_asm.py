"""
真正对比AI生成和Oracle生成的汇编
分析它们的指令序列是否功能等价
"""

import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

def count_instructions(asm):
    """统计汇编指令数量"""
    lines = asm.split('\n')
    # 排除空行和注释
    instructions = [l for l in lines if l.strip() and not l.strip().startswith('.')]
    return len(instructions)

def extract_key_instructions(asm):
    """提取关键指令"""
    lines = asm.split('\n')
    key = []
    for l in lines:
        l = l.strip()
        if any(kw in l for kw in ['li ', 'add', 'sub', 'sw', 'lw', 'beqz', 'bnez', 'ret']):
            key.append(l)
    return key

def main():
    # 加载模型
    print("加载模型...")
    tokenizer = AutoTokenizer.from_pretrained("models/JNCC/final")
    model = AutoModelForCausalLM.from_pretrained("models/JNCC/final")
    if torch.cuda.is_available():
        model = model.cuda()
    model.eval()
    print("模型加载完成\n")

    # 读取测试数据
    with open('dataset/xc_asm_test.jsonl') as f:
        test_cases = [json.loads(line) for line in f]

    print("=" * 70)
    print("AI生成 vs Oracle汇编 对比分析")
    print("=" * 70)

    for i, tc in enumerate(test_cases[:3]):
        print(f"\n{'='*70}")
        print(f"测试 {i+1}: {tc['id']}")
        print(f"{'='*70}")

        xc = tc['xc_source'].replace('\n', ' ')[:60]
        print(f"XC代码: {xc}...")

        oracle_asm = tc['asm_riscv64']

        # 用AI模型生成
        prompt = f"### XC Code:\n{tc['xc_source']}\n\n### Assembly:\n"
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=512, temperature=0.1,
                                     do_sample=False, pad_token_id=tokenizer.eos_token_id)
        ai_asm = tokenizer.decode(outputs[0], skip_special_tokens=True)
        if "### Assembly:" in ai_asm:
            ai_asm = ai_asm.split("### Assembly:")[-1].strip()

        # 对比
        print(f"\nOracle指令数: {count_instructions(oracle_asm)}")
        print(f"AI指令数: {count_instructions(ai_asm)}")

        print(f"\nOracle关键指令:")
        for instr in extract_key_instructions(oracle_asm)[:8]:
            print(f"  {instr}")

        print(f"\nAI关键指令:")
        for instr in extract_key_instructions(ai_asm)[:8]:
            print(f"  {instr}")

        # 简单评估：检查关键指令是否相似
        oracle_keys = set(extract_key_instructions(oracle_asm))
        ai_keys = set(extract_key_instructions(ai_asm))
        overlap = len(oracle_keys & ai_keys)
        union = len(oracle_keys | ai_keys)
        similarity = overlap / union if union > 0 else 0

        print(f"\n指令相似度: {similarity*100:.1f}%")

    print("\n" + "=" * 70)
    print("注意: 这个相似度只是表面指标")
    print("真正的验证需要通过QEMU执行汇编并对比运行结果")
    print("=" * 70)

if __name__ == "__main__":
    main()
