"""带调试的Parser测试"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer, TokenType
from traditional_c.parser import Parser

# 完整测试
print("调试测试: ▢a=♦(b>0)▶◀❖c=1▶▶")
lexer = Lexer()

source = '▢a=♦(b>0)▶◀❖c=1▶▶'
tokens = lexer.tokenize(source)
print(f"Token数量: {len(tokens)}")

# 手动逐步解析
parser = Parser()
parser.tokens = tokens
parser.current_pos = 0

max_steps = 50
step = 0
while step < max_steps and not parser._is_at_end():
    token = parser._peek()
    print(f"Step {step}: pos={parser.current_pos}, token={token['type'].value:12} value={repr(token.get('value', ''))}")

    if parser._check_type(TokenType.KEYWORD):
        kw = token['value']
        print(f"  -> 关键字: {kw}")
        if kw == '▢':
            print("  -> 解析VarDecl...")
            try:
                stmt = parser._parse_var_decl()
                print(f"  -> 成功: {stmt.get('type')} name={stmt.get('name')}")
            except Exception as e:
                print(f"  -> 错误: {e}")
                break
        elif kw == '♦':
            print("  -> 解析IfStmt...")
            try:
                stmt = parser._parse_if_stmt()
                print(f"  -> 成功: {stmt.get('type')}")
            except Exception as e:
                print(f"  -> 错误: {e}")
                import traceback
                traceback.print_exc()
                break
        elif kw == '❖':
            print("  -> 解析ForLoop...")
            try:
                stmt = parser._parse_for_loop()
                print(f"  -> 成功: {stmt.get('type')}")
            except Exception as e:
                print(f"  -> 错误: {e}")
                import traceback
                traceback.print_exc()
                break
        elif kw in ('▶', '◀'):
            print("  -> 跳过括号标记")
            parser._advance()
        else:
            print(f"  -> 未知关键字，跳过")
            parser._advance()
    else:
        print("  -> 非关键字，跳过")
        parser._advance()

    step += 1

if step >= max_steps:
    print(f"\n警告: 达到最大步数 {max_steps}，可能存在无限循环!")
else:
    print(f"\n解析完成! 总共 {step} 步, 最终位置: {parser.current_pos}/{len(tokens)}")
