"""手动恢复测试（§6.4 / RES-01、02、03）。全部使用临时目录。"""

from __future__ import annotations

from datetime import datetime

import pytest

from bond_profit.application import backup_service as backup_service_module
from bond_profit.application.backup_service import BackupService, RestoreError
from bond_profit.infrastructure.backup import create_backup
from bond_profit.infrastructure.backup_state import StateStore
from bond_profit.infrastructure.database import connect

TODAY = datetime.now().strftime("%Y-%m-%d")


@pytest.fixture()
def conn(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield conn
    conn.close()


def _insert(conn, name, code, price_cents, quantity):
    conn.execute(
        "INSERT INTO sales (bond_name, bond_code, sale_date, sale_price_cents, "
        "quantity, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, code, "2026-01-15", price_cents, quantity, "", "t", "t"),
    )
    conn.commit()


@pytest.fixture()
def svc(conn, tmp_path):
    return BackupService(
        conn,
        StateStore(tmp_path / "state.json"),
        tmp_path / "backups" / "auto",
        tmp_path / "backups" / "protected",
    )


@pytest.fixture()
def other_backup(tmp_path):
    """来自另一个库（数据不同）的备份文件：2 条记录、收益 +200.00 元。"""
    other = connect(tmp_path / "other.db")
    _insert(other, "备份里的记录A", "111111", 13000, 10)   # +300.00
    _insert(other, "备份里的记录B", "222222", 9500, 20)    # -100.00
    path = create_backup(other, tmp_path / "src", "manual").path
    other.close()
    return path


def live_rows(conn):
    return conn.execute(
        "SELECT bond_name FROM sales ORDER BY id"
    ).fetchall()


# ---- 正常恢复 -----------------------------------------------------------------

def test_restore_replaces_active_data(conn, svc, other_backup):
    _insert(conn, "当前库的旧记录", "999999", 12000, 5)

    report = svc.restore_from_backup(other_backup)

    assert live_rows(conn) == [("备份里的记录A",), ("备份里的记录B",)]
    assert report.record_count == 2
    assert report.total_profit_cents == 20000  # (13000-10000)*10 + (9500-10000)*20
    assert report.protected.kind == "protected"  # 恢复前保护备份已创建
    assert report.backup.path == other_backup


def test_restore_marks_dirty_and_records_day(svc, other_backup, tmp_path):
    svc.restore_from_backup(other_backup)
    state = StateStore(tmp_path / "state.json").load()
    assert state.dirty is True  # 决策①：次日首次检查生成新自动备份
    assert state.last_auto_backup_date == TODAY


# ---- 拒绝场景（RES-01 / RES-02） ----------------------------------------------

def test_restore_rejects_corrupt_backup(conn, svc, tmp_path):
    """RES-01：损坏备份拒绝恢复，原数据库不变，且不创建保护备份。"""
    _insert(conn, "当前库记录", "999999", 12000, 5)
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a database at all" * 8)

    with pytest.raises(RestoreError):
        svc.restore_from_backup(corrupt)

    assert live_rows(conn) == [("当前库记录",)]
    assert not (tmp_path / "backups" / "protected").exists()  # 校验先行，未动保护目录


def test_restore_rejects_newer_version_backup(conn, svc, tmp_path):
    """RES-02：来自更新版本程序的备份拒绝恢复。"""
    _insert(conn, "当前库记录", "999999", 12000, 5)
    newer = connect(tmp_path / "newer.db")
    newer.execute("PRAGMA user_version = 99")
    newer.commit()
    path = create_backup(newer, tmp_path / "src", "manual").path
    newer.close()

    with pytest.raises(RestoreError):
        svc.restore_from_backup(path)

    assert live_rows(conn) == [("当前库记录",)]


# ---- 失败保护（RES-03） --------------------------------------------------------

def test_failed_restore_keeps_protection_and_live_data(
    conn, svc, other_backup, monkeypatch
):
    """RES-03：恢复中断/失败 → 原数据库可恢复、保护副本存在。"""
    _insert(conn, "当前库记录", "999999", 12000, 5)

    def broken_restore(source_path, temp_db):
        raise RuntimeError("模拟临时恢复中断")

    monkeypatch.setattr(backup_service_module, "_restore_to_temp", broken_restore)
    with pytest.raises(RestoreError):
        svc.restore_from_backup(other_backup)

    protected_dir = svc._protected_dir
    assert len(list(protected_dir.glob("app_*.db"))) == 1  # 保护副本存在
    assert live_rows(conn) == [("当前库记录",)]  # 当前数据未被改动

    monkeypatch.undo()
    report = svc.restore_from_backup(other_backup)  # 修复后可重试成功
    assert report.record_count == 2
