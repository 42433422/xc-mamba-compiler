"""最简单的Parser测试"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

# 测试1: 简单的变量声明
print("测试1: 简单的变量声明")
lexer = Lexer()
parser = Parser()

try:
    tokens = lexer.tokenize('▢x')
    print(f"  Token数量: {len(tokens)}")
    
    import time
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"  成功! 耗时: {elapsed:.4f}s")
    print(f"  AST: {ast}")
except Exception as e:
    print(f"  错误: {e}")

# 测试2: 带初始化的变量声明
print("\n测试2: 带初始化的变量声明")
try:
    tokens = lexer.tokenize('▢x=5')
    print(f"  Token数量: {len(tokens)}")
    
    parser2 = Parser()
    start = time.time()
    ast = parser2.parse(tokens)
    elapsed = time.time() - start
    print(f"  成功! 耗时: {elapsed:.4f}s")
    print(f"  AST: {ast}")
except Exception as e:
    print(f"  错误: {e}")
