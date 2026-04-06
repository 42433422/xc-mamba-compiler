"""测试if语句解析"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

# 测试if语句
print("测试: if语句")
lexer = Lexer()
parser = Parser()

try:
    source = '♦(x>0)▶▶'
    tokens = lexer.tokenize(source)
    print(f"源码: {source}")
    print(f"Token数量: {len(tokens)}")
    
    import time
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"成功! 耗时: {elapsed:.4f}s")
    
    import json
    print(json.dumps(ast, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
