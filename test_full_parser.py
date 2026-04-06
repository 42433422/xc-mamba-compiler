"""完整编译器测试"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser
import time

# 完整测试
print("完整测试: ▢a=♦(b>0)▶◀❖c=1▶▶")
lexer = Lexer()
parser = Parser()

source = '▢a=♦(b>0)▶◀❖c=1▶▶'
print(f"源码: {source}")

try:
    tokens = lexer.tokenize(source)
    print(f"✓ 词法分析完成: {len(tokens)} 个Token")
    
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"✓ 语法分析完成: 耗时 {elapsed:.4f}s")
    
    import json
    print("\nAST结构:")
    print(json.dumps(ast, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
