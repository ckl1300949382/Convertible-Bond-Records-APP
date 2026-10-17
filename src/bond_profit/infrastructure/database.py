"""SQLite 连接与 schema 管理（文档 §5.1）。

数据库路径可注入：默认 %LOCALAPPDATA%/ConvertibleBondProfit/data/app.db，
测试一律传入临时路径。版本迁移策略在阶段 4 实现。
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

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


class DatabaseTooNewError(Exception):
    """数据库版本比当前程序更新：旧程序拒绝写入并提示升级（MIG-03）。"""

    def __init__(self, path: Path, db_version: int) -> None:
        self.path = path
        self.db_version = db_version
        super().__init__(
            f"当前数据库版本（{db_version}）比程序支持的版本（{SCHEMA_VERSION}）更新，"
            "旧程序已停止打开以保护数据。请使用新版程序打开。"
        )


class MigrationError(Exception):
    """版本迁移失败：停止升级，原数据保留（MIG-02）。"""

    def __init__(self, from_version: int) -> None:
        self.from_version = from_version
        super().__init__(
            f"数据库从版本 {from_version} 迁移失败，已停止启动。"
            "原数据未被改动，可尝试通过备份恢复。"
        )


# 迁移注册表（§5.3）：{起始版本: 迁移函数}。
# 迁移函数接收连接，把库结构从该版本升级到 版本+1；版本号由框架在
# 同一事务内提升，迁移失败整体回滚。发布新 schema 版本时在此登记。
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


def run_migrations(conn: sqlite3.Connection, from_version: int) -> None:
    """逐版本事务迁移到 SCHEMA_VERSION；失败抛 MigrationError 并整体回滚。"""
    version = from_version
    while version < SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise MigrationError(version)
        try:
            # 显式 BEGIN：Python sqlite3 的隐式事务只覆盖 DML，
            # DDL（ALTER/CREATE）会自动提交——不显式开事务就无法整体回滚
            conn.execute("BEGIN")
            step(conn)
            # PRAGMA 不支持参数化；值为框架内整数常量，无注入风险
            conn.execute(f"PRAGMA user_version = {version + 1}")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("数据库迁移 %s→%s 失败", version, version + 1, exc_info=True)
            raise MigrationError(version) from exc
        version += 1


def inspect_database(path: Path | str) -> int:
    """启动预检（§5.3）：只读识别完整性与版本，不做任何写入。

    文件不存在返回 0；损坏抛 DatabaseCorruptError。
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return 0
    _check_existing_integrity(path)
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


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

    顺序（§5.3）：完整性检查 → 版本识别 → 过新拒绝写入 →
    按需迁移 → 幂等补齐结构。任何写操作都发生在版本检查之后。
    """
    path = Path(db_path) if db_path is not None else default_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > 0:
        _check_existing_integrity(path)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]

    if current_version == 0:
        # 全新库：直接创建最新结构，不算迁移（§5.3）
        conn.executescript(_SCHEMA)
        # 空参数化不适用于 PRAGMA；值为常量，无注入风险
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        return conn

    if current_version > SCHEMA_VERSION:
        conn.close()
        raise DatabaseTooNewError(path, current_version)

    if current_version < SCHEMA_VERSION:
        try:
            run_migrations(conn, current_version)
        except Exception:
            conn.close()
            raise

    conn.executescript(_SCHEMA)  # 幂等：补齐缺失索引等（IF NOT EXISTS）
    conn.commit()
    return conn
