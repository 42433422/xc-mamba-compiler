#!/usr/bin/env sh
# Run inside Linux (e.g. jncc-riscv-exec Docker). Verifies qemu-riscv64 + RVV.
set -e
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
CC=${RISCV_GCC:-riscv64-linux-gnu-gcc}
QEMU=${RISCV_QEMU:-qemu-riscv64}
SMOKE_S="$ROOT/tools/rvv_smoke.s"
ELF=/tmp/rvv_smoke_$$

cleanup() { rm -f "$ELF"; }
trap cleanup EXIT

"$CC" -static -march=rv64gcv -mabi=lp64d -O0 "$SMOKE_S" -o "$ELF"

# QEMU 8+ user-mode: -cpu rv64,v=true,... ；旧版无该属性会报错。
CPU="${XC_RISCV_QEMU_CPU:-rv64,v=true,vlen=128,vext_spec=v1.0}"
if "$QEMU" -cpu "$CPU" "$ELF" 2>/dev/null; then
  rc=0
elif "$QEMU" -cpu max "$ELF" 2>/dev/null; then
  rc=0
else
  echo "rvv_qemu_smoke: qemu rejected -cpu (need ubuntu:24.04+ / qemu-user 8.x)" >&2
  exit 1
fi
echo "rvv_qemu_smoke: OK (exit $rc)"
