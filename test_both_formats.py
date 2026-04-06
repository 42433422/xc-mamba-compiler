"""Test with proper syntax"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c import TraditionalCCompiler

compiler = TraditionalCCompiler()

# Test with parentheses around for loop
source1 = '▢a ♦(b>0)▶◀❖(c=1;;)▶▶'
print("Test 1: With for loop parens")
print(f"Source: {source1}")
result1 = compiler.compile(source1)
print(f"Success: {result1['success']}")
if not result1['success']:
    print(f"Error: {result1['error']}")
else:
    print("Code:")
    print(result1['results']['optimized_code']['code'])

print("\n" + "=" * 60 + "\n")

# Original test case (may need adjustment)
source2 = '▢a=♦(b>0)▶◀❖c=1▶▶'
print("Test 2: Original format")
print(f"Source: {source2}")
compiler2 = TraditionalCCompiler()
result2 = compiler2.compile(source2)
print(f"Success: {result2['success']}")
if not result2['success']:
    print(f"Error: {result2['error']}")
else:
    print("Code:")
    print(result2['results']['optimized_code']['code'])
