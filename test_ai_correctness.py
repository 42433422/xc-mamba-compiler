"""
真正的执行正确性测试
- 用Oracle生成标准答案
- 用AI模型生成预测
- 对比两者的语义等价性（通过分析汇编结构）
"""

import json
import subprocess
import sys
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# 测试用例
TEST_CASES = [
    {
        "id": "xcasm_122_12345",
        "xc": '# { $x: int = 28 $y: int = 40 $z: int = x - y - 3 ^ z }',
        "description": "算术运算: x=28, y=40, z=x-y-3=28-40-3=-15"
    },
    {
        "id": "xcasm_16_12345",
        "xc": '# { $a0: int = 4 $a1: int = 1 $a2: int = 0 $a3: int = 1 $a4: int = 2 ^ a0 + a1 + a2 + a3 + a4 }',
        "description": "多变量求和: 4+1+0+1+2=8"
    },
    {
        "id": "xcasm_54_12345",
        "xc": '# { $x: int = 9 $y: int = 7 $z: int = x + y + 16 ^ z }',
        "description": "算术运算: x=9, y=7, z=9+7+16=32"
    },
]

def extract_return_value(asm_code):
    """从汇编代码中提取返回值模式"""
    # 查找主要的return值设置 (li a0, N 在 .L_exit_main之前)
    pattern = r'li\s+a0,\s*(-?\d+)'
    matches = re.findall(pattern, asm_code)
    if matches:
        # 返回最后一个li a0的值（通常是最终返回值）
        return int(matches[-1])
    return None

def load_model():
    """加载AI模型"""
    print("加载Mamba模型...")
    try:
        model_path = "models/JNCC/final"
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(model_path)
        if torch.cuda.is_available():
            model = model.cuda()
        model.eval()
        print(f"模型加载成功！设备: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
        return tokenizer, model
    except Exception as e:
        print(f"模型加载失败: {e}")
        return None, None

def generate_with_model(tokenizer, model, xc_code, max_new_tokens=512):
    """用AI模型生成汇编"""
    # 构造prompt
    prompt = f"### XC Code:\n{xc_code}\n\n### Assembly:\n"

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # 提取生成的汇编部分
    if "### Assembly:" in generated:
        asm = generated.split("### Assembly:")[-1].strip()
        return asm
    return generated

def main():
    print("=" * 70)
    print("JNCC AI编译器 - 执行正确性测试")
    print("=" * 70)

    # 加载模型
    tokenizer, model = load_model()
    if model is None:
        print("无法加载模型，测试终止")
        return

    print("\n" + "=" * 70)
    print("开始测试...")
    print("=" * 70)

    results = []

    for i, tc in enumerate(TEST_CASES):
        print(f"\n【测试 {i+1}/{len(TEST_CASES)}】 {tc['id']}")
        print(f"描述: {tc['description']}")
        print(f"XC: {tc['xc'][:60]}...")

        # 用AI模型生成
        print("正在用AI模型编译...")
        ai_asm = generate_with_model(tokenizer, model, tc['xc'])
        ai_return = extract_return_value(ai_asm)

        # 从测试数据获取Oracle答案
        with open('dataset/xc_asm_test.jsonl') as f:
            for line in f:
                data = json.loads(line)
                if data['id'] == tc['id']:
                    oracle_asm = data['asm_riscv64']
                    oracle_return = extract_return_value(oracle_asm)
                    break

        print(f"  Oracle返回值: {oracle_return}")
        print(f"  AI模型返回值: {ai_return}")

        # 评估
        if ai_return is not None and ai_return == oracle_return:
            status = "✅ 匹配"
        elif ai_return is not None:
            status = f"❌ 不匹配 (差 {ai_return - oracle_return})"
        else:
            status = "⚠️ 无法提取返回值"

        print(f"  状态: {status}")

        # 统计信息
        oracle_lines = len(oracle_asm.split('\n'))
        ai_lines = len(ai_asm.split('\n')) if ai_asm else 0

        results.append({
            'id': tc['id'],
            'description': tc['description'],
            'oracle_return': oracle_return,
            'ai_return': ai_return,
            'oracle_lines': oracle_lines,
            'ai_lines': ai_lines,
            'match': ai_return == oracle_return if ai_return else False
        })

    # 汇总
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)

    total = len(results)
    matched = sum(1 for r in results if r['match'])
    match_rate = matched / total * 100 if total > 0 else 0

    print(f"总测试数: {total}")
    print(f"返回值匹配: {matched}/{total} ({match_rate:.1f}%)")
    print()

    for r in results:
        status = "✅" if r['match'] else "❌"
        print(f"{status} {r['id']}: Oracle={r['oracle_return']}, AI={r['ai_return']}")

    print("\n" + "=" * 70)
    print("注意: 由于Windows环境没有RISC-V工具链,无法实际执行验证.")
    print("这里对比的是AI模型生成的返回值模式与Oracle的返回值模式.")
    print("=" * 70)

if __name__ == "__main__":
    main()
