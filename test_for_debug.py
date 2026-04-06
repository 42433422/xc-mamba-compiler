"""For循环详细调试"""

import sys
import time
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer, TokenType
from traditional_c.parser import Parser

print("For Loop Debug")
print("=" * 50)

lexer = Lexer()
source = '❖(c=1;;)▶▶'
tokens = lexer.tokenize(source)

print(f"Source: {source}")
print(f"Tokens ({len(tokens)}):")
for i, t in enumerate(tokens):
    print(f"  {i:2d}: {t['type'].value:12} {repr(t['value']):6} pos={t['position']}")

print("\nStarting parse...")
parser = Parser()
parser.tokens = tokens
parser.current_pos = 0

try:
    # 手动逐步执行 _parse_for_loop
    print("\n1. Consuming ❖ (for keyword)")
    for_token = parser._advance()
    print(f"   pos={parser.current_pos}, token={for_token['value']}")
    
    print("\n2. Expecting (")
    assert parser._check_type(TokenType.DELIMITER) and parser._peek()['value'] == '('
    parser._advance()
    print(f"   pos={parser.current_pos}")
    
    print("\n3. Parsing init expression...")
    init = None
    if not (parser._check_type(TokenType.DELIMITER) and parser._peek()['value'] == ';'):
        print(f"   Current token: {parser._peek()['type'].value} {repr(parser._peek()['value'])}")
        init = parser._parse_expression()
        print(f"   init={init}")
        print(f"   pos={parser.current_pos}")
    
    print("\n4. Expecting ; (after init)")
    print(f"   Current token: {parser._peek()['type'].value} {repr(parser._peek()['value'])}")
    parser._expect_delimiter(';')
    print(f"   pos={parser.current_pos}")
    
    print("\n5. Parsing condition...")
    condition = None
    if not (parser._check_type(TokenType.DELIMITER) and parser._peek()['value'] == ';'):
        condition = parser._parse_expression()
    print(f"   condition={condition}")
    
    print("\n6. Expecting ; (after condition)")
    print(f"   Current token: {parser._peek()['type'].value} {repr(parser._peek()['value'])}")
    parser._expect_delimiter(';')
    print(f"   pos={parser.current_pos}")
    
    print("\n7. Parsing update...")
    update = None
    if not (parser._check_type(TokenType.DELIMITER) and parser._peek()['value'] == ')'):
        update = parser._parse_expression()
    print(f"   update={update}")
    
    print("\n8. Expecting )")
    print(f"   Current token: {parser._peek()['type'].value} {repr(parser._peek()['value'])}")
    assert parser._check_type(TokenType.DELIMITER) and parser._peek()['value'] == ')'
    parser._advance()
    print(f"   pos={parser.current_pos}")
    
    print("\n9. Checking for ◀ (block start)")
    print(f"   Current token: {parser._peek()['type'].value} {repr(parser._peek()['value'])}")
    if parser._check_type(TokenType.KEYWORD) and parser._peek()['value'] == '◀':
        parser._advance()
        print(f"   Consumed ◀, pos={parser.current_pos}")
    
    print("\n10. Parsing body (block)")
    start_time = time.time()
    body = parser._parse_block()
    elapsed = time.time() - start_time
    print(f"   body={body}")
    print(f"   pos={parser.current_pos}")
    print(f"   Took {elapsed:.4f}s")
    
    print("\n✓ SUCCESS!")
    
except Exception as e:
    print(f"\n✗ ERROR at pos={parser.current_pos}: {e}")
    import traceback
    traceback.print_exc()
