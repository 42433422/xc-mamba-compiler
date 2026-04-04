#!/usr/bin/env python3
"""
合并多个 JSONL：按 id 去重，**后出现的文件覆盖先出现的同 id**（便于 supplement 覆盖 train）。
流式读取，内存仅保留已见 id 集合与当前行（大 train 友好）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set


def iter_nonempty_lines(path: Path) -> Iterable[str]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield line


def merge_files(paths: List[Path], out: Path) -> Dict[str, int]:
    """
    第一个文件决定**输出顺序**（通常为 train）；后续文件**覆盖同 id 内容**；
    仅出现在后续文件中的 id **按出现顺序追加**在末尾。
    """
    if not paths:
        return {"unique_ids": 0, "files_merged": 0}

    last_line: Dict[str, str] = {}
    train_order: List[str] = []
    for line in iter_nonempty_lines(paths[0]):
        row = json.loads(line)
        rid = row.get("id") or ""
        if not rid:
            continue
        train_order.append(rid)
        last_line[rid] = line

    extras: List[str] = []
    seen_extra: Set[str] = set(train_order)
    for p in paths[1:]:
        for line in iter_nonempty_lines(p):
            row = json.loads(line)
            rid = row.get("id") or ""
            if not rid:
                continue
            last_line[rid] = line
            if rid not in seen_extra:
                extras.append(rid)
                seen_extra.add(rid)

    out.parent.mkdir(parents=True, exist_ok=True)
    out_lines = [last_line[rid] for rid in train_order if rid in last_line]
    out_lines.extend(last_line[rid] for rid in extras if rid in last_line)

    with open(out, "w", encoding="utf-8") as wf:
        for line in out_lines:
            wf.write(line + "\n")

    return {"unique_ids": len(out_lines), "files_merged": len(paths)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge JSONL with last-id-wins semantics.")
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--in", dest="inputs", type=str, nargs="+", required=True, metavar="PATH")
    args = ap.parse_args()

    paths = [Path(x) for x in args.inputs]
    for p in paths:
        if not p.is_file():
            print(f"Missing: {p}", file=sys.stderr)
            return 2

    stats = merge_files(paths, Path(args.out))
    print(json.dumps({"out": args.out, **stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
