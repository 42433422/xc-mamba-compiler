"""简单测试Parser"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

# 测试词法分析器
print("测试Parser...")
lexer = Lexer()
source_code = '▢a=♦(b>0)▶◀❖c=1▶▶'
print(f"源代码: {source_code}")

try:
    tokens = lexer.tokenize(source_code)
    print(f"词法分析完成: {len(tokens)} 个Token")

    parser = Parser()
    ast = parser.parse(tokens)
    print(f"语法分析成功!")
    import json
    print(json.dumps(ast, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
