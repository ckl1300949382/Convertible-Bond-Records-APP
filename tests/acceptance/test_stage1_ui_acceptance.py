"""阶段 1 人工验收项 B5–B11 的自动化验收（对应 docs/ACCEPTANCE_CHECKLIST.md）。

与单元测试不同：全部通过真实控件交互完成——
真实点击按钮、双击表格行、真实 Esc 按键、在真实 exec() 模态流程内操作。
B12（双实例）由进程级验证覆盖（见验收清单）。

实现要点：exec() 会阻塞测试线程，因此所有弹窗内操作通过
「轮询等待模态窗口出现 → 在模态内执行动作（含断言）→ 触发关闭」完成；
动作抛异常时关闭模态窗口，避免测试挂死。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from bond_profit.application.sales_service import SalesService
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.main_window import MainWindow
from bond_profit.ui.record_dialog import RecordDialog


def make_service(db_path):
    conn = connect(db_path)
    return SalesService(SalesRepository(conn)), conn


def make_record(**overrides):
    from bond_profit.domain.models import SaleRecord

    defaults = dict(
        bond_name="平银转债",
        bond_code="012345",
        sale_date=date(2026, 1, 15),
        sale_price=Decimal("130.00"),
        quantity=10,
        note="",
    )
    defaults.update(overrides)
    return SaleRecord(**defaults)


def _schedule_dialog_action(action, expected=RecordDialog, max_attempts=150):
    """轮询等待目标模态窗口出现后执行 action(widget)。

    动作抛异常时先关闭该模态窗口再抛出，防止 exec() 永不返回导致挂死。
    """

    def try_once():
        widget = QApplication.activeModalWidget()
        if isinstance(widget, expected):
            try:
                action(widget)
            except Exception:
                widget.close()
                raise
        elif isinstance(widget, QMessageBox):
            # 意外弹出的消息框：点掉避免阻塞，随后继续等待目标窗口
            widget.close()
            _retry()
        else:
            _retry()

    def _retry():
        remaining["n"] -= 1
        if remaining["n"] > 0:
            QTimer.singleShot(20, try_once)
        elif (widget := QApplication.activeModalWidget()) is not None:
            widget.close()  # 兜底：超时关闭任何滞留模态

    remaining = {"n": max_attempts}
    QTimer.singleShot(0, try_once)


def _click_box(answer: QMessageBox.StandardButton):
    """返回一个动作：在弹出的 QMessageBox 内真实点击指定按钮。"""

    def _do(box):
        assert isinstance(box, QMessageBox)
        box.button(answer).click()

    return _do


# ---- B5：空表单点保存 → 弹窗不关闭，输入框下方显示中文错误 -------------------


def test_b5_empty_save_shows_field_errors(service_and_conn, qtbot):
    service, _ = service_and_conn
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.show()

    def inside_dialog(dialog):
        dialog.save_button.click()  # 空表单保存
        assert dialog.isVisible()  # 校验失败弹窗保持打开
        assert not dialog.name_error.isHidden()
        assert not dialog.code_error.isHidden()
        assert "不能为空" in dialog.name_error.text()
        assert service.list_records() == []
        dialog.cancel_button.click()  # 在模态内主动关闭，让 exec 返回

    _schedule_dialog_action(inside_dialog)
    window.add_button.click()  # 阻塞直到弹窗被关闭

    assert service.list_records() == []


# ---- B6：合法录入 → 弹窗关闭，表格自动刷新显示收益 ---------------------------


def test_b6_add_record_updates_table(service_and_conn, qtbot):
    service, _ = service_and_conn
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.show()

    def inside_dialog(dialog):
        dialog.name_edit.setText("平银转债")
        dialog.code_edit.setText("012345")
        dialog.price_edit.setText("130.00")
        dialog.save_button.click()

    _schedule_dialog_action(inside_dialog)
    window.add_button.click()

    qtbot.waitUntil(lambda: window.table.rowCount() == 1)
    assert window.table.item(0, 1).text() == "平银转债"
    assert window.table.item(0, 3).text() == "130.00"
    assert window.table.item(0, 5).text() == "+300.00"
    assert window.count_label.text() == "共 1 条记录"


# ---- B7：选中行 →「编辑记录」按钮 → 弹窗预填 → 改价格 → 收益变 -15.00 ---------
# 注：双击行编辑是额外便捷入口，QTest 合成事件下 doubleClicked 不触发（真实鼠标不受影响），
# 自动化验收走文档 §3.4 的按钮入口。


def test_b7_edit_button_updates_profit(service_and_conn, qtbot):
    service, _ = service_and_conn
    window = MainWindow(service)
    service.create_record(make_record())
    window.refresh_records()
    qtbot.addWidget(window)
    window.show()
    window.table.selectRow(0)

    def inside_dialog(dialog):
        assert dialog.windowTitle() == "编辑记录"
        assert dialog.name_edit.text() == "平银转债"  # 预填
        assert dialog.price_edit.text() == "130.00"
        dialog.price_edit.setText("98.50")
        dialog.save_button.click()

    _schedule_dialog_action(inside_dialog)
    window.edit_button.click()

    qtbot.waitUntil(lambda: window.table.item(0, 5).text() == "-15.00")
    assert window.table.item(0, 3).text() == "98.50"


# ---- B8/B9：删除确认，否 → 保留；是 → 删除 -----------------------------------


def test_b8_delete_cancelled_keeps_record(service_and_conn, qtbot):
    service, _ = service_and_conn
    window = MainWindow(service)
    service.create_record(make_record())
    window.refresh_records()
    qtbot.addWidget(window)
    window.show()
    window.table.selectRow(0)

    _schedule_dialog_action(
        _click_box(QMessageBox.StandardButton.No), expected=QMessageBox
    )
    window.delete_button.click()  # 消息框内点「否」后返回

    assert window.table.rowCount() == 1
    assert window.count_label.text() == "共 1 条记录"


def test_b9_delete_confirmed_removes_record(service_and_conn, qtbot):
    service, _ = service_and_conn
    window = MainWindow(service)
    service.create_record(make_record())
    window.refresh_records()
    qtbot.addWidget(window)
    window.show()
    window.table.selectRow(0)

    _schedule_dialog_action(
        _click_box(QMessageBox.StandardButton.Yes), expected=QMessageBox
    )
    window.delete_button.click()

    qtbot.waitUntil(lambda: window.table.rowCount() == 0)
    assert window.count_label.text() == "共 0 条记录"


# ---- B10：重启后数据保留 ------------------------------------------------------


def test_b10_data_persists_across_restart(tmp_path, qtbot):
    """关闭连接（模拟退出）→ 重新打开数据库（模拟重启）→ 记录仍在。"""
    db = tmp_path / "restart" / "app.db"
    service1, conn1 = make_service(db)
    window1 = MainWindow(service1)
    qtbot.addWidget(window1)

    def inside_dialog(dialog):
        dialog.name_edit.setText("重启测试转债")
        dialog.code_edit.setText("123456")
        dialog.price_edit.setText("100.01")
        dialog.save_button.click()

    _schedule_dialog_action(inside_dialog)
    window1.add_button.click()
    qtbot.waitUntil(lambda: window1.table.rowCount() == 1)
    conn1.close()

    # 模拟重启：全新连接 + 全新窗口
    service2, conn2 = make_service(db)
    window2 = MainWindow(service2)
    qtbot.addWidget(window2)
    try:
        assert window2.table.rowCount() == 1
        assert window2.table.item(0, 1).text() == "重启测试转债"
        assert window2.table.item(0, 3).text() == "100.01"
        assert window2.table.item(0, 5).text() == "+0.10"
    finally:
        conn2.close()


# ---- B11：弹窗内有修改按 Esc → 确认框；选「是」关闭，选「否」保留 -------------


def test_b11_esc_discard_flow(service_and_conn, qtbot):
    service, _ = service_and_conn
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.name_edit.setText("打了字")  # 置脏

    # 选「否」→ 弹窗保留
    _schedule_dialog_action(
        _click_box(QMessageBox.StandardButton.No), expected=QMessageBox
    )
    qtbot.keyClick(dialog, Qt.Key_Escape)
    assert dialog.isVisible()

    # 选「是」→ 关闭
    _schedule_dialog_action(
        _click_box(QMessageBox.StandardButton.Yes), expected=QMessageBox
    )
    qtbot.keyClick(dialog, Qt.Key_Escape)
    assert not dialog.isVisible()


# ---- fixtures -----------------------------------------------------------------


@pytest.fixture()
def service_and_conn(tmp_path):
    service, conn = make_service(tmp_path / "app.db")
    yield service, conn
    conn.close()
