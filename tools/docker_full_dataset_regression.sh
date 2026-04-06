#!/usr/bin/env sh
# 在 jncc-riscv-exec 容器内对 dataset/xc_asm_all.jsonl（200 条）跑金标 QEMU + Oracle 自测对拍（指标 A/B）。
# 用法（仓库根目录）:
#   docker build -f Dockerfile.jncc-riscv-exec -t jncc-riscv-exec .
#   sh tools/docker_full_dataset_regression.sh
set -eu
IMG="${JNCC_RISCV_IMAGE:-jncc-riscv-exec}"
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
docker run --rm -v "$ROOT:/work" -w /work "$IMG" python3 tools/jncc_linux_validate_gold_asm_jsonl.py \
  --jsonl dataset/xc_asm_all.jsonl \
  --out reports/linux_exec_validate_gold_full.json
docker run --rm -v "$ROOT:/work" -w /work "$IMG" python3 tools/run_eval_pipeline.py \
  --oracle_self_test \
  --jsonl dataset/xc_asm_all.jsonl \
  --limit 0 \
  --prompt_mode teacher \
  --proximity \
  --pred_out reports/pred_oracle_self_xc_asm_all.jsonl \
  --report_out reports/linux_exec_validate_oracle_self_xc_asm_all.json
docker run --rm -v "$ROOT:/work" -w /work "$IMG" python3 tools/aggregate_full_dataset_compare.py
