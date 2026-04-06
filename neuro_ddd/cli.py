"""Minimal CLI: ``python -m neuro_ddd doctor``."""

from __future__ import annotations

import argparse
import importlib
import sys


def cmd_doctor() -> int:
    mods = [
        "neuro_ddd",
        "neuro_ddd.core.bus",
        "neuro_ddd.ddd.application",
        "neuro_ddd.resilience",
        "neuro_ddd.observability.tracing",
    ]
    ok = True
    for m in mods:
        try:
            importlib.import_module(m)
            print(f"ok  {m}")
        except Exception as e:
            ok = False
            print(f"err {m}: {e}", file=sys.stderr)
    try:
        importlib.import_module("opentelemetry.trace")
        print("ok  opentelemetry (optional SDK present)")
    except Exception:
        print("info opentelemetry not installed (optional)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="neuro-ddd")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor", help="verify imports and optional OTel")
    d.set_defaults(func=cmd_doctor)
    args = p.parse_args(argv)
    return int(args.func())


if __name__ == "__main__":
    raise SystemExit(main())
