"""Complete working test"""

import sys
sys.path.insert(0, 'e:/X语音')

from traditional_c import TraditionalCCompiler
import json

compiler = TraditionalCCompiler()

# Complete test with all variables declared
source = '▢a ▢b ▢c ♦(b>0)▶◀❖(c=1;;)▶▶'
print("=" * 60)
print("Complete Compilation Test")
print("=" * 60)
print(f"Source: {source}")
print()

result = compiler.compile(source)

print(f"Success: {result['success']}")
print(f"Total time: {result['total_time']:.6f}s")
print()

if result['success']:
    print("-" * 60)
    print("Stage Timings:")
    print("-" * 60)
    for stage, timing in result['timings'].items():
        print(f"  {stage:20s}: {timing:.6f}s")

    print()
    print("-" * 60)
    print("Generated C Code:")
    print("-" * 60)
    code = result['results']['optimized_code']['code']
    print(code)

    print()
    print("-" * 60)
    print("Optimization Stats:")
    print("-" * 60)
    stats = result['results']['optimized_code']['optimization_stats']
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print()
    print("-" * 60)
    print("Pipeline Status:")
    print("-" * 60)
    status = compiler.get_pipeline_status()
    print(json.dumps(status, indent=2))

else:
    print("FAILED!")
    print(f"Error: {result['error']}")
    print()
    print("-" * 60)
    print("Execution Log (last 5):")
    print("-" * 60)
    for log in result['execution_log'][-5:]:
        print(f"  [{log['stage']}] {log['event']}")

print()
print("=" * 60)
