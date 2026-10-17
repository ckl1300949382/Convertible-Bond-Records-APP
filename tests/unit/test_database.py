"""数据库连接、损坏检测与版本迁移测试（§5.2 / §5.3 / §6.5 / MIG-01～03）。"""

from __future__ import annotations

import sqlite3

import pytest

from bond_profit.infrastructure import database
from bond_profit.infrastructure.database import (
    SCHEMA_VERSION,
    DatabaseCorruptError,
    DatabaseTooNewError,
    MigrationError,
    connect,
    inspect_database,
)


def test_fresh_db_created_with_schema_version(tmp_path):
    conn = connect(tmp_path / "app.db")
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == SCHEMA_VERSION
    finally:
        conn.close()
    assert (tmp_path / "app.db").is_file()


def test_reconnect_existing_db_preserves_data(tmp_path):
    conn = connect(tmp_path / "app.db")
    conn.execute(
        "INSERT INTO sales (bond_name, bond_code, sale_date, sale_price_cents, "
        "quantity, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("平银转债", "012345", "2026-01-15", 13000, 10, "", "t", "t"),
    )
    conn.commit()
    conn.close()

    conn = connect(tmp_path / "app.db")  # 再次打开：完整性检查通过，数据仍在
    try:
        count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_corrupt_db_refuses_to_open_and_file_preserved(tmp_path):
    """§6.5：损坏库拒绝打开，原文件原样保留，不得静默建空库覆盖。"""
    path = tmp_path / "app.db"
    garbage = b"this is definitely not a sqlite database" * 10
    path.write_bytes(garbage)

    with pytest.raises(DatabaseCorruptError):
        connect(path)

    assert path.read_bytes() == garbage  # 损坏文件未被改动或替换


# ---- 版本迁移（§5.3 / MIG-01～03） ---------------------------------------------

def _seed_v1_db(path):
    conn = connect(path)
    conn.executemany(
        "INSERT INTO sales (bond_name, bond_code, sale_date, sale_price_cents, "
        "quantity, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("平银转债", "012345", "2026-01-15", 13000, 10, "", "t", "t"),
            ("中信转债", "123456", "2026-02-01", 9500, 20, "亏损", "t", "t"),
        ],
    )
    conn.commit()
    return conn


def test_old_db_migrates_successfully(tmp_path, monkeypatch):
    """MIG-01：旧版数据库升级成功，记录与统计不丢失。"""
    path = tmp_path / "app.db"
    _seed_v1_db(path).close()

    def v1_to_v2(conn):
        conn.execute("ALTER TABLE sales ADD COLUMN trade_account TEXT NOT NULL DEFAULT ''")

    monkeypatch.setattr(database, "SCHEMA_VERSION", 2)
    monkeypatch.setattr(database, "MIGRATIONS", {1: v1_to_v2})

    conn = connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 2  # 记录不丢
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sales)")}
        assert "trade_account" in cols  # 迁移步骤生效
    finally:
        conn.close()


def test_migration_failure_stops_and_preserves_data(tmp_path, monkeypatch):
    """MIG-02：迁移失败停止升级，原数据保留、版本号不变。"""
    path = tmp_path / "app.db"
    _seed_v1_db(path).close()

    def broken(conn):
        # 先成功执行一条 DDL，再中途失败——验证显式 BEGIN 能整体回滚 DDL
        conn.execute("ALTER TABLE sales ADD COLUMN extra TEXT NOT NULL DEFAULT ''")
        raise RuntimeError("模拟迁移中途失败")

    monkeypatch.setattr(database, "SCHEMA_VERSION", 2)
    monkeypatch.setattr(database, "MIGRATIONS", {1: broken})

    with pytest.raises(MigrationError):
        connect(path)

    conn = sqlite3.connect(path)  # 未打补丁状态下检查原文件
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1  # 版本未提升
        assert conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 2
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sales)")}
        assert "extra" not in cols  # 成功执行过的 DDL 也已整体回滚
    finally:
        conn.close()


def test_missing_migration_step_raises(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    _seed_v1_db(path).close()
    monkeypatch.setattr(database, "SCHEMA_VERSION", 2)
    monkeypatch.setattr(database, "MIGRATIONS", {})  # 未登记迁移步骤

    with pytest.raises(MigrationError):
        connect(path)


def test_too_new_db_refused_without_writes(tmp_path):
    """MIG-03：旧程序打开过新数据库 → 拒绝写入并提示升级，数据不变。"""
    path = tmp_path / "app.db"
    conn = _seed_v1_db(path)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    with pytest.raises(DatabaseTooNewError):
        connect(path)

    check = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        assert check.execute("PRAGMA user_version").fetchone()[0] == 99
        assert check.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 2
    finally:
        check.close()


def test_inspect_database_readonly_versions(tmp_path):
    missing = tmp_path / "missing.db"
    assert inspect_database(missing) == 0

    path = tmp_path / "app.db"
    _seed_v1_db(path).close()
    assert inspect_database(path) == 1

    newer = connect(tmp_path / "newer.db")
    newer.execute("PRAGMA user_version = 7")
    newer.commit()
    newer.close()
    assert inspect_database(tmp_path / "newer.db") == 7  # 预检只识别，不判断

    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"junk" * 32)
    with pytest.raises(DatabaseCorruptError):
        inspect_database(garbage)
