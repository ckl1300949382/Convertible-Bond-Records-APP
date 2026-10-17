"""备份与恢复页及其主窗口接线测试（§6 UI / 批次 16）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QMessageBox

import bond_profit.ui.backup_page as backup_page_module
from bond_profit.application.backup_service import BackupService
from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.infrastructure.backup import BackupInfo, create_backup
from bond_profit.infrastructure.backup_state import StateStore
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.backup_page import BackupPage
from bond_profit.ui.main_window import MainWindow


@pytest.fixture()
def conn(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield conn
    conn.close()


def make_info(tmp_path, name="app_20261017_120000_aabbcc.db", verified=True):
    path = tmp_path / name
    path.write_bytes(b"x")
    return BackupInfo(path, "auto", "2026-10-17 12:00:00", 3, 1, verified)


# ---- 页面本体 -----------------------------------------------------------------

def test_populate_backups_fills_columns(qtbot, tmp_path):
    page = BackupPage()
    qtbot.addWidget(page)
    page.populate_backups([
        make_info(tmp_path),
        make_info(tmp_path, verified=False, name="app_20261017_130000_ddeeff.db"),
    ])

    assert page.table.rowCount() == 2
    assert page.table.item(0, 1).text() == "自动"
    assert page.table.item(0, 4).text() == "通过"
    assert page.table.item(1, 4).text() == "未通过"  # 损坏备份状态可见
    assert "共 2 份备份" in page.count_label.text()


def test_kind_labels(qtbot, tmp_path):
    page = BackupPage()
    qtbot.addWidget(page)
    info = make_info(tmp_path)
    page.populate_backups([info])
    assert page.table.item(0, 1).text() == "自动"

    protected = BackupInfo(info.path, "protected", info.created_at, 3, 1, True)
    page.populate_backups([protected])
    assert page.table.item(0, 1).text() == "保护"


def test_manual_backup_emits_chosen_dir(qtbot, tmp_path, monkeypatch):
    page = BackupPage()
    qtbot.addWidget(page)
    captured = []
    page.manual_backup_requested.connect(captured.append)

    dest = tmp_path / "手动目录"
    monkeypatch.setattr(
        backup_page_module.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *a, **k: str(dest)),
    )
    page.backup_now_button.click()
    assert captured == [str(dest)]


def test_manual_backup_cancelled_emits_nothing(qtbot, monkeypatch):
    page = BackupPage()
    qtbot.addWidget(page)
    captured = []
    page.manual_backup_requested.connect(captured.append)

    monkeypatch.setattr(
        backup_page_module.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *a, **k: ""),  # 用户取消
    )
    page.backup_now_button.click()
    assert captured == []


def test_restore_requires_selection(qtbot, monkeypatch):
    page = BackupPage()
    qtbot.addWidget(page)
    captured = []
    page.restore_requested.connect(captured.append)
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: None)
    )

    page.restore_button.click()  # 未选择任何行
    assert captured == []


def test_restore_confirm_yes_emits_path(qtbot, tmp_path, monkeypatch):
    page = BackupPage()
    qtbot.addWidget(page)
    captured = []
    page.restore_requested.connect(captured.append)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )

    infos = [make_info(tmp_path), make_info(tmp_path, name="app_20261016_090000_112233.db")]
    page.populate_backups(infos)
    page.table.selectRow(1)
    page.restore_button.click()
    assert captured == [str(infos[1].path)]


def test_restore_confirm_no_emits_nothing(qtbot, tmp_path, monkeypatch):
    page = BackupPage()
    qtbot.addWidget(page)
    captured = []
    page.restore_requested.connect(captured.append)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )

    page.populate_backups([make_info(tmp_path)])
    page.table.selectRow(0)
    page.restore_button.click()
    assert captured == []


# ---- 主窗口接线 ----------------------------------------------------------------

@pytest.fixture()
def backup_env(tmp_path):
    conn = connect(tmp_path / "app.db")
    backup = BackupService(
        conn,
        StateStore(tmp_path / "state.json"),
        tmp_path / "backups" / "auto",
        tmp_path / "backups" / "protected",
    )
    yield backup, conn
    conn.close()


def _make_window(backup_env, qtbot):
    backup, conn = backup_env
    service = SalesService(SalesRepository(conn))
    window = MainWindow(service, ExcelService(service), backup_service=backup)
    qtbot.addWidget(window)
    return window


def test_nav_contains_backup_page_and_timer(backup_env, qtbot):
    window = _make_window(backup_env, qtbot)

    assert window.nav_list.count() == 3
    assert window.nav_list.item(2).text() == "备份与恢复"
    assert window._backup_timer.interval() == MainWindow._AUTO_BACKUP_INTERVAL_MS
    assert window._backup_timer.isActive()


def test_timer_not_started_without_backup_service(tmp_path, qtbot):
    conn = connect(tmp_path / "app.db")
    try:
        service = SalesService(SalesRepository(conn))
        window = MainWindow(service, ExcelService(service))
        qtbot.addWidget(window)
        assert not window._backup_timer.isActive()
    finally:
        conn.close()


def test_manual_backup_via_window(backup_env, qtbot, tmp_path, monkeypatch):
    window = _make_window(backup_env, qtbot)
    messages = []
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: messages.append(a))
    )
    dest = tmp_path / "手动目录"
    monkeypatch.setattr(
        backup_page_module.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *a, **k: str(dest)),
    )

    window.backup_page.backup_now_button.click()

    assert len(list(dest.glob("app_*.db"))) == 1  # 备份文件生成在自选目录
    assert any("备份成功" in str(a) for a in messages)


def test_auto_check_slot_creates_backup(backup_env, qtbot):
    window = _make_window(backup_env, qtbot)
    window._backup.mark_dirty()  # 模拟已有数据变更

    window._on_auto_backup_check()

    auto_dir = window._backup._auto_dir
    assert len(list(auto_dir.glob("app_*.db"))) == 1
    assert window.backup_page.table.rowCount() == 1  # 列表已刷新
    assert "自动备份完成" in window.statusBar().currentMessage()


def test_auto_check_failure_shows_status_message(backup_env, qtbot, monkeypatch):
    window = _make_window(backup_env, qtbot)
    from bond_profit.infrastructure.backup import BackupError

    def broken(*args, **kwargs):
        raise BackupError("备份创建失败，请检查磁盘空间与写入权限")

    monkeypatch.setattr(window._backup, "run_auto_backup", broken)
    window._on_auto_backup_check()

    assert "自动备份失败" in window.statusBar().currentMessage()  # 不弹窗、不阻断


def test_restore_via_window_replaces_data_and_refreshes(
    backup_env, qtbot, tmp_path, monkeypatch
):
    window = _make_window(backup_env, qtbot)
    service = window._service
    from bond_profit.domain.models import SaleRecord

    service.create_record(SaleRecord(
        bond_name="当前库旧记录", bond_code="999999",
        sale_date=date(2026, 3, 1), sale_price=Decimal("120.00"), quantity=5, note="",
    ))

    # 备份来自另一个库（2 条记录），放在保护目录以便出现在列表中
    other = connect(tmp_path / "other.db")
    other.execute(
        "INSERT INTO sales (bond_name, bond_code, sale_date, sale_price_cents, "
        "quantity, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("备份记录A", "111111", "2026-01-15", 13000, 10, "", "2026-01-15T10:00:00", "2026-01-15T10:00:00"),
    )
    other.commit()
    backup_path = create_backup(other, window._backup._protected_dir, "protected").path
    other.close()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: None)
    )
    window._refresh_backup_list()
    window.backup_page.table.selectRow(0)
    window.backup_page.restore_button.click()

    names = [r.bond_name for r in service.list_records()]
    assert names == ["备份记录A"]  # 数据已替换
    assert window.table.rowCount() == 1  # 总览表格同步刷新（§66）
    assert window.backup_page.table.rowCount() == 2  # 列表含恢复前保护备份

    # 决策①：恢复后置脏、记录当日已备份
    state = window._backup._state_store.load()
    assert state.dirty is True
    assert state.last_auto_backup_date != ""


def test_restore_cancelled_via_window(backup_env, qtbot, tmp_path, monkeypatch):
    window = _make_window(backup_env, qtbot)
    service = window._service
    from bond_profit.domain.models import SaleRecord

    service.create_record(SaleRecord(
        bond_name="当前库记录", bond_code="999999",
        sale_date=date(2026, 3, 1), sale_price=Decimal("120.00"), quantity=5, note="",
    ))
    other = connect(tmp_path / "other.db")
    backup_path = create_backup(other, window._backup._protected_dir, "protected").path
    other.close()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    window._refresh_backup_list()
    window.backup_page.table.selectRow(0)
    window.backup_page.restore_button.click()

    assert [r.bond_name for r in service.list_records()] == ["当前库记录"]
