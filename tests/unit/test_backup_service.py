"""备份服务层测试（§6.1 / BAK-01、02、03）。全部使用临时目录。"""

from __future__ import annotations

from datetime import datetime

import pytest

from bond_profit.application import backup_service as backup_service_module
from bond_profit.application.backup_service import BackupService
from bond_profit.infrastructure.backup import BackupError
from bond_profit.infrastructure.backup_state import BackupState, StateStore
from bond_profit.infrastructure.database import connect

DAY1 = datetime(2026, 10, 17, 9, 0, 0)
DAY2 = datetime(2026, 10, 18, 9, 0, 0)


@pytest.fixture()
def conn(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield conn
    conn.close()


@pytest.fixture()
def svc(conn, tmp_path):
    return BackupService(
        conn,
        StateStore(tmp_path / "state.json"),
        tmp_path / "backups" / "auto",
        tmp_path / "backups" / "protected",
    )


# ---- 自动备份策略（§6.1） -----------------------------------------------------

def test_first_run_backs_up_once_per_day(svc, tmp_path):
    """首次运行（状态缺失按脏处理）当天生成一份自动备份；当天再查不再生成（BAK-01）。"""
    auto_dir = tmp_path / "backups" / "auto"
    assert svc.run_auto_backup(DAY1) is not None
    assert svc.run_auto_backup(DAY1) is None  # 当天已成功
    assert len(list(auto_dir.glob("app_*.db"))) == 1


def test_no_backup_across_days_without_changes(svc):
    """跨天但无变更：不生成新备份（§6.1 只在有变更时备份）。"""
    assert svc.run_auto_backup(DAY1) is not None
    assert svc.run_auto_backup(DAY2) is None


def test_cross_day_backup_after_changes(svc, tmp_path):
    """BAK-02：跨天保持运行且有变更 → 次日检查生成新备份。"""
    auto_dir = tmp_path / "backups" / "auto"
    svc.run_auto_backup(DAY1)
    svc.mark_dirty()  # 模拟当天后续数据变更（跨天期间）
    assert svc.run_auto_backup(DAY2) is not None
    assert len(list(auto_dir.glob("app_*.db"))) == 2


def test_failed_backup_keeps_state_and_retries(svc, tmp_path, monkeypatch):
    """BAK-03：失败不计当日成功次数、状态不变；重试成功后计数。"""
    state_path = tmp_path / "state.json"
    svc.mark_dirty()

    def broken(*args, **kwargs):
        raise BackupError("备份创建失败，请检查磁盘空间与写入权限")

    monkeypatch.setattr(backup_service_module, "create_backup", broken)
    with pytest.raises(BackupError):
        svc.run_auto_backup(DAY1)

    state = StateStore(state_path).load()
    assert state.last_auto_backup_date == ""  # 未计入当天
    assert state.dirty is True

    monkeypatch.undo()
    assert svc.run_auto_backup(DAY1) is not None  # 重试成功
    state = StateStore(state_path).load()
    assert state.last_auto_backup_date == "2026-10-17"
    assert state.dirty is False


# ---- 脏标记与手动备份 ---------------------------------------------------------

def test_mark_dirty_persists(svc, tmp_path):
    svc.mark_dirty()
    assert StateStore(tmp_path / "state.json").load().dirty is True


def test_manual_backup_clears_dirty(svc, tmp_path):
    """手动备份成功后清脏：之后无变更则自动备份不再触发。"""
    dest = tmp_path / "手动备份目录"
    svc.mark_dirty()
    info = svc.run_manual_backup(dest)

    assert info.kind == "manual"
    assert len(list(dest.glob("app_*.db"))) == 1
    assert svc.run_auto_backup(DAY1) is None  # 未脏，跳过


# ---- 状态存储（阶段 4） -------------------------------------------------------

def test_state_store_corrupt_falls_back_to_safe_defaults(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{broken json", encoding="utf-8")
    assert StateStore(state_path).load() == BackupState()  # 脏=True、从未备份


def test_state_store_roundtrip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save(BackupState(last_auto_backup_date="2026-10-17", dirty=False))
    loaded = StateStore(tmp_path / "state.json").load()
    assert loaded == BackupState(last_auto_backup_date="2026-10-17", dirty=False)
