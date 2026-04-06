"""简单For循环parse()测试"""

import sys
import time
sys.path.insert(0, 'e:/X语音')

# 强制重新导入模块
if 'traditional_c' in sys.modules:
    del sys.modules['traditional_c']
if 'traditional_c.parser' in sys.modules:
    del sys.modules['traditional_c.parser']
if 'traditional_c.lexer' in sys.modules:
    del sys.modules['traditional_c.lexer']

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

print("Test: For loop parse()")
lexer = Lexer()
parser = Parser()

source = '❖(c=1;;)▶▶'
print(f"Source: {source}")

tokens = lexer.tokenize(source)
print(f"Tokens: {len(tokens)}")

start = time.time()
try:
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"SUCCESS in {elapsed:.4f}s")
    print(f"AST type: {ast['type']}")
    print(f"Body length: {len(ast['body'])}")
except Exception as e:
    elapsed = time.time() - start
    print(f"FAIL after {elapsed:.4f}s: {e}")
    import traceback
    traceback.print_exc()
