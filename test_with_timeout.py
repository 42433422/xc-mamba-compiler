"""带超时的完整编译器测试"""

import sys
import signal
import time
sys.path.insert(0, 'e:/X语音')

# 设置超时处理（仅Unix-like系统）
def timeout_handler(signum, frame):
    raise TimeoutError("Parser执行超时!")

# Windows不支持signal.alarm，使用时间检查
from traditional_c import TraditionalCCompiler

print("=" * 60)
print("传统C语言线性编译器 - 完整测试")
print("=" * 60)

compiler = TraditionalCCompiler()
source_code = '▢a=♦(b>0)▶◀❖c=1▶▶'
print(f"源代码: {source_code}")
print()

MAX_TIME = 2.0  # 最大执行时间（秒）

start_time = time.time()
try:
    result = compiler.compile(source_code)
    elapsed = time.time() - start_time
    
    if elapsed > MAX_TIME:
        print(f"✗ 执行时间过长: {elapsed:.2f}s > {MAX_TIME}s")
    else:
        print(f"✓ 编译成功!")
        print(f"  耗时: {elapsed:.6f}秒")
        print(f"  成功: {result['success']}")
        
        if result['success']:
            print(f"\n  各阶段耗时:")
            for stage, timing in result['timings'].items():
                print(f"    {stage}: {timing:.6f}s")
            
            code = result['results']['optimized_code']['code']
            print(f"\n  生成的C代码:")
            for line in code.split('\n'):
                print(f"    {line}")
            
            stats = result['results']['optimized_code'].get('optimization_stats', {})
            print(f"\n  优化统计: {stats}")
        else:
            print(f"\n  错误信息: {result['error']}")

except TimeoutError as e:
    elapsed = time.time() - start_time
    print(f"✗ {e} (已运行{elapsed:.2f}s)")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"✗ 异常: {e} (运行了{elapsed:.2f}s)")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
