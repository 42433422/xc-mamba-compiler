"""简单测试传统C语言编译器"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer

# 测试词法分析器
print("测试词法分析器...")
lexer = Lexer()
source_code = '▢a=♦(b>0)▶◀❖c=1▶▶'
print(f"源代码: {source_code}")

try:
    tokens = lexer.tokenize(source_code)
    print(f"成功! 生成 {len(tokens)} 个Token")
    for i, token in enumerate(tokens):
        print(f"  {i}: {token['type'].value:12} | {repr(token['value']):6} | pos={token['position']}")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
