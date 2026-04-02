"""JNCC 结构化退出码与错误域（CLI 与自动化共用）。"""

from __future__ import annotations

from enum import IntEnum


class JNCCExitCode(IntEnum):
    OK = 0
    PARSE_ERROR = 1
    ORACLE_UNSUPPORTED = 2
    ASSEMBLE_FAILED = 3
    MODEL_FAILED = 4
    SANITY_FAILED = 5
    INTERNAL = 6
    QEMU_FAILED = 7


ERROR_DOMAIN = "jncc.v1"

# Oracle / 前端常见拒因（用于门控分桶与日志对齐，非穷举）
UNSUPPORTED_REASON_CATALOG = frozenset(
    {
        "PrintStmt",
        "InputStmt",
        "StructDef",
        "IndexAccess",
        "MemberAccess",
        "unsupported_type_name",
        "malloc",
        "仅允许调用本程序内函数",
    }
)
