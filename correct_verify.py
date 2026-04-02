"""
正确的验证方法：
从C代码中提取真正的返回值（第一个return语句，不是main末尾的return 0）
"""

import json
import re

def extract_c_return(c_code):
    """
    从C代码中提取真正的返回值
    main函数末尾的 return 0 不算，那是默认的
    """
    # 找到所有 return 语句
    returns = re.findall(r'return\s+([^;]+);', c_code)

    if not returns:
        return None

    # 返回第一个（真正的程序逻辑返回值）
    # 最后一个通常是 return 0;
    first_return = returns[0].strip()

    # 尝试计算数值
    try:
        # 直接是数字
        return int(first_return)
    except:
        pass

    # 尝试解析表达式
    # 例如: ((((a0 + a1) + a2) + a3) + a4)
    expr = first_return.replace('(', '').replace(')', '').replace(' ', '')

    # 检查是否是简单的变量
    if expr.isdigit():
        return int(expr)

    # 尝试解析加法链
    if '+' in expr:
        parts = expr.split('+')
        try:
            return sum(int(p) for p in parts)
        except:
            pass

    return None

def main():
    with open('dataset/xc_asm_test.jsonl') as f:
        test_cases = [json.loads(line) for line in f]

    print("=" * 70)
    print("正确验证测试数据")
    print("=" * 70)

    passed = 0
    failed = 0

    for tc in test_cases[:10]:
        tc_id = tc['id']
        c_ref = tc['c_reference']

        # 提取C代码中的第一个return值
        expected = extract_c_return(c_ref)

        print(f"\n[{tc_id}]")
        print(f"  C代码第一个return: {expected}")

        # 手动计算XC逻辑
        xc = tc['xc_source']
        returns = re.findall(r'\^\s*([a-zA-Z0-9_+\-*\/\(\)]+?)(?:\s|$|\})', xc)
        if returns:
            expr = returns[-1].strip()
            print(f"  XC返回表达式: {expr}")

        # 从汇编中提取实际会被执行的li a0值
        asm = tc['asm_riscv64']

        # 找到.L_exit_main标签之前最近的li a0（跳转会跳过后面的li a0 0）
        lines = asm.split('\n')
        exit_idx = -1
        for i, line in enumerate(lines):
            if '.L_exit_main:' in line:
                exit_idx = i
                break

        if exit_idx > 0:
            # 向前找最后一个li a0
            for i in range(exit_idx - 1, -1, -1):
                match = re.search(r'li\s+a0,\s*(-?\d+)', lines[i])
                if match:
                    actual_return = int(match.group(1))
                    print(f"  汇编实际返回值: {actual_return}")
                    break

        # 判断
        if expected is not None:
            if expected == actual_return:
                print(f"  ✅ 匹配")
                passed += 1
            else:
                print(f"  ❌ 不匹配 (C逻辑={expected}, 汇编={actual_return})")
                failed += 1
        else:
            print(f"  ⚠️ 无法解析C代码")

    print("\n" + "=" * 70)
    print(f"汇总: {passed}通过 / {failed}失败")
    print("=" * 70)

if __name__ == "__main__":
    main()
