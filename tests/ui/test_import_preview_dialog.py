"""导入预览对话框测试（§4.4）：逐行状态、统计、错误禁用、确认导入。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook
from PySide6.QtWidgets import QDialog, QMessageBox

import bond_profit.ui.import_preview_dialog as dialog_module
from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import RepositoryError, SalesRepository
from bond_profit.ui.import_preview_dialog import ImportPreviewDialog

_HEADERS = ["转债名称", "转债代码", "卖出日期", "卖出价格", "卖出数量", "备注"]


@pytest.fixture()
def service(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield SalesService(SalesRepository(conn))
    conn.close()


@pytest.fixture()
def excel(service):
    return ExcelService(service)


def save_rows(tmp_path, rows, name="import.xlsx"):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "卖出记录"
    sheet.append(_HEADERS)
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    workbook.save(path)
    return str(path)


def valid_row(**overrides):
    values = ["平银转债", "012345", date(2026, 1, 15), Decimal("130.00"), 10, ""]
    for key, value in overrides.items():
        values[_HEADERS.index(key)] = value
    return values


def make_dialog(excel, service, rows, tmp_path):
    preview = excel.preview_import(save_rows(tmp_path, rows))
    return ImportPreviewDialog(excel, preview)


# ---- 显示 ---------------------------------------------------------------------

def test_summary_and_rows_display(tmp_path, excel, service, qtbot):
    dialog = make_dialog(
        excel, service,
        [valid_row(), valid_row()],  # 第二行文件内重复
        tmp_path,
    )
    qtbot.addWidget(dialog)

    summary = dialog.summary_label.text()
    assert "预计新增 1 笔" in summary
    assert "重复跳过 1 笔" in summary
    assert "预计净收益变化 +300.00 元" in summary

    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 1).text() == "可导入"
    assert dialog.table.item(0, 2).text() == "平银转债"
    assert dialog.table.item(0, 5).text() == "130.00"
    assert dialog.table.item(1, 1).text() == "重复跳过"
    assert dialog.table.item(1, 2).text() == "平银转债"  # 重复行保留内容供对照
    assert "相同" in dialog.table.item(1, 8).text()
    assert dialog.confirm_button.isEnabled()


def test_error_rows_disable_confirm(tmp_path, excel, service, qtbot):
    dialog = make_dialog(
        excel, service,
        [valid_row(), valid_row(**{"卖出日期": "2026/01/15"})],
        tmp_path,
    )
    qtbot.addWidget(dialog)
    dialog.show()

    assert not dialog.confirm_button.isEnabled()
    assert dialog.error_hint.isVisible()
    assert "无法识别" in dialog.table.item(1, 8).text()
    assert dialog.table.item(1, 1).text() == "错误"


# ---- 确认导入 -------------------------------------------------------------------

def test_confirm_imports_and_accepts(tmp_path, excel, service, qtbot, monkeypatch):
    monkeypatch.setattr(
        dialog_module.QMessageBox, "information", lambda *a, **k: None
    )
    dialog = make_dialog(excel, service, [valid_row()], tmp_path)
    qtbot.addWidget(dialog)

    dialog.confirm_button.click()

    assert len(service.list_records()) == 1
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_commit_failure_keeps_dialog_open(
    tmp_path, excel, service, qtbot, monkeypatch
):
    warnings = []
    monkeypatch.setattr(
        dialog_module.QMessageBox, "warning",
        lambda parent, title, text: warnings.append((title, text)),
    )

    def fail(_preview):
        raise RepositoryError("数据库写入失败，本次导入未保存任何记录")

    monkeypatch.setattr(dialog_module.ExcelService, "commit_import", fail)
    dialog = make_dialog(excel, service, [valid_row()], tmp_path)
    qtbot.addWidget(dialog)

    dialog.confirm_button.click()

    assert "导入失败" == warnings[0][0]
    assert dialog.result() == QDialog.DialogCode.Rejected  # 未 accept，保持打开
