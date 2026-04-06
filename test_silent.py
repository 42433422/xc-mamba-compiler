"""Silent test - write result to file"""

import sys
import time
sys.path.insert(0, 'e:/X语音')

from traditional_c.lexer import Lexer
from traditional_c.parser import Parser

lexer = Lexer()
parser = Parser()

source = '❖(c=1;;)▶▶'
tokens = lexer.tokenize(source)

start = time.time()
result_file = 'test_result.txt'

try:
    ast = parser.parse(tokens)
    elapsed = time.time() - start

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write('SUCCESS\n')
        f.write('Time: %.6f\n' % elapsed)
        ast_type = ast['type']
        f.write('AST type: %s\n' % ast_type)
        body_len = len(ast['body'])
        f.write('Body len: %d\n' % body_len)
except Exception as e:
    elapsed = time.time() - start

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write('FAIL\n')
        f.write('Time: %.6f\n' % elapsed)
        f.write('Error: %s\n' % str(e))
