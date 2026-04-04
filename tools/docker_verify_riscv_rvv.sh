#!/usr/bin/env sh
# 在 jncc-riscv-exec 容器内执行：打印 QEMU 版本并尝试 RVV 冒烟（需 QEMU 8+ / ubuntu:24.04 镜像）。
set -e
echo "=== qemu-riscv64 ==="
qemu-riscv64 --version | head -1
echo "=== rvv_qemu_smoke (may fail on qemu-user 6.x) ==="
if sh tools/rvv_qemu_smoke.sh; then
  echo "RVV smoke: OK"
else
  echo "RVV smoke: FAILED — 重建镜像: docker build -f Dockerfile.jncc-riscv-exec -t jncc-riscv-exec ." >&2
  exit 1
fi
