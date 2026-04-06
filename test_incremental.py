"""最小化完整测试"""

import sys
import time
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

def test_simple():
    """测试简单的if语句（无嵌套for）"""
    print("Test 1: Simple if")
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize('♦(x>0)▶▶')
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"  OK: {elapsed:.4f}s")
    return True

def test_if_with_block():
    """测试带空代码块的if"""
    print("Test 2: If with empty block")
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize('♦(x>0)▶◀▶')
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"  OK: {elapsed:.4f}s")
    return True

def test_var_and_if():
    """测试变量声明+if语句"""
    print("Test 3: Var decl + if")
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize('▢a ♦(b>0)▶▶')
    start = time.time()
    ast = parser.parse(tokens)
    elapsed = time.time() - start
    print(f"  OK: {elapsed:.4f}s")
    return True

def test_for_loop():
    """测试单独的for循环"""
    print("Test 4: For loop only")
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize('❖(c=1;;)▶▶')
    start = time.time()
    try:
        ast = parser.parse(tokens)
        elapsed = time.time() - start
        print(f"  OK: {elapsed:.4f}s")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAIL ({elapsed:.4f}s): {e}")
        return False

# 运行所有测试
tests = [
    test_simple,
    test_if_with_block,
    test_var_and_if,
    test_for_loop,
]

for i, test in enumerate(tests):
    try:
        result = test()
        if not result:
            break
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        break

print("\nAll tests completed!")
