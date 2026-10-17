"""SQLite 连接与 schema 管理（文档 §5.1）。

数据库路径可注入：默认 %LOCALAPPDATA%/ConvertibleBondProfit/data/app.db，
测试一律传入临时路径。版本迁移策略在阶段 4 实现。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    bond_name TEXT NOT NULL
        CHECK (length(trim(bond_name)) BETWEEN 1 AND 50),
    bond_code TEXT NOT NULL
        CHECK (bond_code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'),
    sale_date TEXT NOT NULL
        CHECK (sale_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    sale_price_cents INTEGER NOT NULL CHECK (sale_price_cents > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales (sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_bond_code ON sales (bond_code);
"""


class DatabaseCorruptError(Exception):
    """数据库文件存在但已损坏。必须停止正常使用，引导手动恢复（§6.5）。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            "数据库文件已损坏，为保护数据已停止启动。原文件已原样保留，"
            "请勿删除或改动它；可在其他正常会话中通过备份恢复功能处理。"
        )


def default_database_path() -> Path:
    """真实运行时的数据库路径。"""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("未找到 LOCALAPPDATA 环境变量，无法确定数据目录")
    return Path(base) / "ConvertibleBondProfit" / "data" / "app.db"


def _check_existing_integrity(path: Path) -> None:
    """已存在的非空库文件先做完整性检查，再允许任何写入（§6.5）。

    损坏时抛出 DatabaseCorruptError，原文件原样保留供排查；
    不得静默创建空库覆盖（§5.3）。
    """
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise DatabaseCorruptError(path) from exc
    finally:
        conn.close()
    if result != "ok":
        raise DatabaseCorruptError(path)


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """打开连接；目录与表结构不存在时创建。

    已存在的非空库文件先通过完整性检查，损坏则拒绝打开。
    """
    path = Path(db_path) if db_path is not None else default_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > 0:
        _check_existing_integrity(path)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)

    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version == 0:
        # 空参数化不适用于 PRAGMA；值为常量，无注入风险
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    conn.commit()
    return conn
