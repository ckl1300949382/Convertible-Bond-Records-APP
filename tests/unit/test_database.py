"""数据库连接与损坏检测测试（§5.2 / §6.5）。"""

from __future__ import annotations

import pytest

from bond_profit.infrastructure.database import (
    SCHEMA_VERSION,
    DatabaseCorruptError,
    connect,
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
