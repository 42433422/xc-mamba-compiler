"""测试表达式解析"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

print("测试: 表达式解析")
lexer = Lexer()
parser = Parser()

# 测试1: 简单表达式
try:
    tokens = lexer.tokenize('x>0')
    parser.tokens = tokens
    parser.current_pos = 0
    expr = parser._parse_expression()
    print(f"✓ 'x>0' -> {expr}")
except Exception as e:
    print(f"✗ 'x>0' 错误: {e}")

# 测试2: 赋值表达式 (for循环中的c=1)
try:
    parser2 = Parser()
    tokens = lexer.tokenize('c=1')
    parser2.tokens = tokens
    parser2.current_pos = 0
    expr = parser2._parse_expression()
    print(f"✓ 'c=1' -> {expr}")
except Exception as e:
    print(f"✗ 'c=1' 错误: {e}")
    import traceback
    traceback.print_exc()

# 测试3: 遇到关键字时
try:
    parser3 = Parser()
    # 模拟: 表达式后面跟着关键字 ♦
    tokens = [
        {'type': lexer.__class__.__module__.split('.')[0] if False else None},
    ]
    # 直接手动构造tokens
    from traditional_c.lexer import TokenType
    tokens = [
        {'type': TokenType.IDENTIFIER, 'value': 'b', 'position': 0},
        {'type': TokenType.OPERATOR, 'value': '>', 'position': 1},
        {'type': TokenType.NUMBER, 'value': '0', 'position': 2},
        {'type': TokenType.KEYWORD, 'value': '♦', 'position': 3},  # 关键字
        {'type': TokenType.EOF, 'value': '', 'position': 4},
    ]
    parser3.tokens = tokens
    parser3.current_pos = 0
    expr = parser3._parse_expression()
    print(f"✓ 'b>0♦' -> {expr} (应该在♦处停止)")
    print(f"  当前位置: {parser3.current_pos}")
except Exception as e:
    print(f"✗ 'b>0♦' 错误: {e}")
    import traceback
    traceback.print_exc()
