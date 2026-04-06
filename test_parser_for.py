"""测试For循环解析"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

# 测试for循环
print("测试: For循环")
lexer = Lexer()
parser = Parser()

try:
    # 简单的for循环: ❖(c=1;;)▶▶
    source = '❖(c=1;;)▶▶'
    tokens = lexer.tokenize(source)
    print(f"源码: {source}")
    print(f"Tokens:")
    for i, t in enumerate(tokens):
        print(f"  {i}: {t['type'].value:12} {repr(t['value'])}")
    
    import time
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"\n成功! 耗时: {elapsed:.4f}s")
    
    import json
    print(json.dumps(ast, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
