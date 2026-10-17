"""主窗口测试：表格显示、删除确认（REC-03）、刷新联动。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QMessageBox

from bond_profit.application.sales_service import SalesService
from bond_profit.domain.models import SaleRecord
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.main_window import MainWindow


@pytest.fixture()
def service(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield SalesService(SalesRepository(conn))
    conn.close()


def make_record(**overrides) -> SaleRecord:
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


def test_empty_window_shows_zero_count(service, qtbot):
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window.table.rowCount() == 0
    assert window.count_label.text() == "共 0 条记录"


def test_refresh_shows_records_with_profit(service, qtbot):
    service.create_record(make_record())
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "平银转债"
    assert window.table.item(0, 5).text() == "+300.00"  # (130-100)*10
    assert window.count_label.text() == "共 1 条记录"


def test_delete_cancelled_keeps_record(service, qtbot, monkeypatch):
    service.create_record(make_record())
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.table.selectRow(0)

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    window._on_delete()

    assert window.table.rowCount() == 1


def test_delete_confirmed_removes_record(service, qtbot, monkeypatch):
    service.create_record(make_record())
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.table.selectRow(0)

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    window._on_delete()

    assert window.table.rowCount() == 0
    assert window.count_label.text() == "共 0 条记录"


def test_delete_without_selection_does_nothing(service, qtbot):
    service.create_record(make_record())
    window = MainWindow(service)
    qtbot.addWidget(window)

    window._on_delete()  # 无选中行，不应弹确认也不应删除
    assert window.table.rowCount() == 1
