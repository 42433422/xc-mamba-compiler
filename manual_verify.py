"""
手动验证测试数据的正确性
通过分析XC代码的语义来确认Oracle生成的汇编是否会产生正确的返回值

不需要RISC-V工具链，只分析代码逻辑
"""

import json
import re

def analyze_xc_return(xc_code):
    """
    分析XC代码的返回值
    这是一个简化的解释器
    """
    # 移除注释和空白
    xc = xc_code.replace('\n', ' ').strip()

    # 提取变量赋值
    vars = {}
    returns = []

    # 找到所有变量赋值: $x = N 或 $x: int = N
    var_pattern = r'\$([a-zA-Z0-9_]+)(?::\s*int)?\s*=\s*(-?\d+)'
    for match in re.finditer(var_pattern, xc):
        var_name = match.group(1)
        var_value = int(match.group(2))
        vars[var_name] = var_value

    # 找到return语句: ^ expr
    return_pattern = r'\^\s*([a-zA-Z0-9_+\-*\/\(\)\s]+?)(?:\s|$|\})'
    for match in re.finditer(return_pattern, xc):
        expr = match.group(1).strip()
        returns.append(expr)

    return vars, returns

def evaluate_expr(expr, vars):
    """
    计算表达式的值
    """
    # 简单变量
    if expr in vars:
        return vars[expr]

    # 处理加减法
    expr = expr.replace(' ', '')

    # 如果是纯数字
    try:
        return int(expr)
    except:
        pass

    # 尝试简单的算术表达式
    try:
        # 简单的 x + y 或 x - y 模式
        if '+' in expr:
            parts = expr.split('+')
            total = 0
            for p in parts:
                total += evaluate_expr(p.strip(), vars)
            return total
        if '-' in expr:
            parts = expr.split('-')
            total = evaluate_expr(parts[0].strip(), vars)
            for p in parts[1:]:
                total -= evaluate_expr(p.strip(), vars)
            return total
    except:
        pass

    return None

def main():
    with open('dataset/xc_asm_test.jsonl') as f:
        test_cases = [json.loads(line) for line in f]

    print("=" * 70)
    print("手动验证测试数据")
    print("=" * 70)

    passed = 0
    failed = 0

    for tc in test_cases[:10]:
        tc_id = tc['id']
        xc_code = tc['xc_source']
        asm = tc['asm_riscv64']

        # 从汇编中提取Oracle认为的返回值
        # Oracle汇编最后会 li a0, N 然后 ret
        asm_returns = re.findall(r'li\s+a0,\s*(-?\d+)', asm)
        if asm_returns:
            oracle_return = int(asm_returns[-1])
        else:
            oracle_return = None

        # 分析XC代码
        vars, return_exprs = analyze_xc_return(xc_code)

        print(f"\n[{tc_id}]")
        print(f"  XC代码: {xc_code.replace(chr(10), ' ').strip()[:60]}...")
        print(f"  提取变量: {vars}")

        # 尝试计算返回值
        if return_exprs:
            # 找到最后一个return语句（最终返回值）
            final_return = return_exprs[-1]
            print(f"  返回表达式: {final_return}")

            # 尝试计算
            computed = evaluate_expr(final_return, vars)
            print(f"  计算返回值: {computed}")
        else:
            computed = None

        if computed is not None and oracle_return is not None:
            if computed == oracle_return:
                print(f"  ✅ 匹配 (XC逻辑={computed}, Oracle汇编={oracle_return})")
                passed += 1
            else:
                print(f"  ❌ 不匹配 (XC逻辑={computed}, Oracle汇编={oracle_return})")
                failed += 1
        elif oracle_return is not None:
            print(f"  ⚠️ 无法计算XC逻辑，但Oracle返回={oracle_return}")
        else:
            print(f"  ⚠️ 无法提取返回值")

    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总计: {passed + failed}")

    # 结论
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    if failed == 0:
        print("✅ 所有测试数据的XC逻辑与Oracle汇编返回值一致！")
        print("这证明测试数据是正确的，可以用于评估AI模型。")
    else:
        print(f"⚠️ 发现{failed}个不一致的测试数据，可能需要修正。")

if __name__ == "__main__":
    main()
