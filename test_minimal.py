"""Minimal test"""

import sys
sys.path.insert(0, 'e:/X语音')

print("Step 1: Importing modules...")

from traditional_c.lexer import Lexer
print("Step 2: Lexer imported")

from traditional_c.parser import Parser
print("Step 3: Parser imported")

print("Step 4: Creating objects...")
lexer = Lexer()
parser = Parser()
print("Step 5: Objects created")

source = '❖(c=1;;)▶▶'
print(f"Step 6: Tokenizing '{source}'...")
tokens = lexer.tokenize(source)
print(f"Step 7: Got {len(tokens)} tokens")

print("Step 8: Parsing...")
ast = parser.parse(tokens)
print(f"Step 9: Parsed! Type={ast['type']}")
