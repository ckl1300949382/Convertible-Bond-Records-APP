"""新增/编辑弹窗测试（§3.4：校验提示、失败保留输入、Esc 确认放弃）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QMessageBox

from bond_profit.application.sales_service import SalesService
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.record_dialog import RecordDialog


@pytest.fixture()
def service(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield SalesService(SalesRepository(conn))
    conn.close()


def test_add_mode_defaults(service, qtbot):
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "新增记录"
    assert dialog.date_edit.date() == QDate.currentDate()
    assert dialog.quantity_spin.value() == 10
    assert not dialog._dirty


def test_invalid_save_shows_errors_and_stays_open(service, qtbot):
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)
    dialog.show()

    dialog._on_save()  # 空表单保存

    assert dialog.isVisible()
    assert not dialog.name_error.isHidden()
    assert service.list_records() == []


def test_non_numeric_price_shows_field_error(service, qtbot):
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)

    dialog.name_edit.setText("平银转债")
    dialog.code_edit.setText("012345")
    dialog.price_edit.setText("abc")
    dialog._on_save()

    assert not dialog.price_error.isHidden()
    assert "数字" in dialog.price_error.text()
    assert service.list_records() == []


def test_valid_add_saves_and_accepts(service, qtbot):
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)

    dialog.name_edit.setText("  平银转债  ")
    dialog.code_edit.setText("012345")
    dialog.price_edit.setText("130.00")
    dialog._on_save()

    records = service.list_records()
    assert len(records) == 1
    assert records[0].bond_name == "平银转债"  # 标准化生效
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_edit_mode_prefills_and_updates(service, qtbot):
    from bond_profit.domain.models import SaleRecord

    created = service.create_record(
        SaleRecord(
            bond_name="平银转债",
            bond_code="012345",
            sale_date=date(2026, 1, 15),
            sale_price=Decimal("130.00"),
            quantity=10,
        )
    ).record

    dialog = RecordDialog(service, record=created)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "编辑记录"
    assert dialog.name_edit.text() == "平银转债"
    assert dialog.price_edit.text() == "130.00"

    dialog.price_edit.setText("110.00")
    dialog._on_save()

    assert service.list_records()[0].sale_price == Decimal("110.00")


def test_esc_with_unsaved_changes_confirms(service, qtbot, monkeypatch):
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.name_edit.setText("打了字")  # 置脏

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    dialog.reject()
    assert dialog.isVisible()  # 选择「否」→ 弹窗保留

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    dialog.reject()
    assert not dialog.isVisible()  # 选择「是」→ 关闭


def test_esc_without_changes_closes_directly(service, qtbot):
    dialog = RecordDialog(service)
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.reject()  # 未修改，不弹确认
    assert not dialog.isVisible()
