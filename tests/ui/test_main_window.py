"""主窗口测试：表格显示、删除确认（REC-03）、刷新联动、统计卡片与空状态。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMessageBox

import bond_profit.ui.main_window as main_window_module
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


# ---- 阶段 2：搜索 / 筛选 / 排序 / 分页（§3.3，STA-01 前置，UI-01） ----------


def seed_many(service, count=25) -> None:
    for i in range(count):
        service.create_record(
            make_record(
                bond_name=f"转债{i:02d}号",
                bond_code=f"1234{i:02d}",
                sale_price=Decimal(f"10{i % 10}.50"),
            )
        )


def test_pagination_first_page_and_label(service, qtbot):
    seed_many(service)
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window.table.rowCount() == 20
    assert window.page_label.text() == "第 1 / 2 页"
    assert window.count_label.text() == "共 25 条记录"
    assert not window.prev_button.isEnabled()
    assert window.next_button.isEnabled()


def test_pagination_next_and_prev(service, qtbot):
    seed_many(service)
    window = MainWindow(service)
    qtbot.addWidget(window)

    window.next_button.click()
    assert window.table.rowCount() == 5
    assert window.page_label.text() == "第 2 / 2 页"
    assert window.prev_button.isEnabled()
    assert not window.next_button.isEnabled()

    window.prev_button.click()
    assert window.table.rowCount() == 20
    assert window.page_label.text() == "第 1 / 2 页"


def test_search_filters_table_and_resets_page(service, qtbot):
    seed_many(service)
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.next_button.click()

    # ASCII 键入走真实 textEdited 信号路径（中文键事件在 Windows 下不稳定）
    qtbot.keyClicks(window.search_input, "05")
    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "转债05号"
    assert window.count_label.text() == "共 1 条记录"
    assert window.page_label.text() == "第 1 / 1 页"  # 筛选变更回到第一页


def test_search_chinese_keyword_via_handler(service, qtbot):
    """中文关键词搜索（避免 keyClicks 发送中文键事件）。"""
    seed_many(service)
    window = MainWindow(service)
    qtbot.addWidget(window)

    window.search_input.setText("转债05")
    window._on_search_changed()
    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "转债05号"


def test_search_no_match_shows_empty(service, qtbot):
    seed_many(service)
    window = MainWindow(service)
    qtbot.addWidget(window)

    window.search_input.setText("不存在的名称")
    window._on_search_changed()
    assert window.table.rowCount() == 0
    assert window.page_label.text() == "第 1 / 1 页"


def test_year_filter_and_month_combo_state(service, qtbot):
    service.create_record(make_record(sale_date=date(2026, 1, 15)))
    service.create_record(make_record(sale_date=date(2025, 6, 1)))
    window = MainWindow(service)
    qtbot.addWidget(window)

    # 初始：全部年份，月份下拉不可用
    assert window.year_combo.currentData() is None
    assert not window.month_combo.isEnabled()

    # 选择 2025 年 → 只剩 1 条，月份下拉可用
    index = window.year_combo.findData(2025)
    window.year_combo.setCurrentIndex(index)
    assert window.month_combo.isEnabled()
    assert window.table.rowCount() == 1
    assert window.table.item(0, 0).text() == "2025-06-01"
    assert window.count_label.text() == "共 1 条记录"

    # 再选 6 月 → 仍是这条；选其他月 → 空
    month_index = window.month_combo.findData(6)
    window.month_combo.setCurrentIndex(month_index)
    assert window.table.rowCount() == 1
    month_index = window.month_combo.findData(7)
    window.month_combo.setCurrentIndex(month_index)
    assert window.table.rowCount() == 0

    # 切回全部年份 → 月份下拉复位并禁用，显示全部
    window.year_combo.setCurrentIndex(0)
    assert not window.month_combo.isEnabled()
    assert window.table.rowCount() == 2


def test_header_click_sorts_by_price(service, qtbot):
    service.create_record(make_record(bond_name="低", sale_price=Decimal("101.00")))
    service.create_record(make_record(bond_name="高", sale_price=Decimal("150.00")))
    service.create_record(make_record(bond_name="中", sale_price=Decimal("120.00")))
    window = MainWindow(service)
    qtbot.addWidget(window)

    window._on_header_clicked(3)  # 卖出单价降序
    assert window.table.item(0, 1).text() == "高"

    window._on_header_clicked(3)  # 再点一次 → 升序
    assert window.table.item(0, 1).text() == "低"


def test_header_click_non_sortable_column_ignored(service, qtbot):
    seed_many(service, 3)
    window = MainWindow(service)
    qtbot.addWidget(window)

    window._on_header_clicked(1)  # 名称列不允许排序，保持默认日期降序
    assert window._sort_key == "date"
    assert window._sort_desc is True


def test_delete_last_item_on_last_page_adjusts_page(service, qtbot, monkeypatch):
    seed_many(service, 21)  # 两页：20 + 1
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.next_button.click()
    assert window.page_label.text() == "第 2 / 2 页"

    window.table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    window._on_delete()

    # 剩 20 条 → 只剩一页，页码自动调整
    assert window.count_label.text() == "共 20 条记录"
    assert window.page_label.text() == "第 1 / 1 页"
    assert window.table.rowCount() == 20


def test_ctrl_f_focuses_search_input(service, qtbot):
    """Ctrl+F 快捷键聚焦搜索框。

    QShortcut 对合成键事件不响应（同阶段 1 双击的已知限制），
    因此直接验证快捷键的 activated 接线；按键匹配由 Qt 平台层保证，人工抽检。
    """
    seed_many(service, 3)
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.table.setFocus()
    assert window.focusWidget() is window.table  # 焦点起始于表格

    shortcut = window.findChild(QShortcut)
    assert shortcut is not None and shortcut.key() == QKeySequence("Ctrl+F")
    shortcut.activated.emit()
    assert window.focusWidget() is window.search_input


# ---- 阶段 2 批次 6：统计卡片与空状态（§3.2，STA-01 / REC-02） ----------------


def test_stat_cards_show_global_values(service, qtbot):
    today = date.today()
    this_month = today.replace(day=1)
    service.create_record(make_record(sale_date=this_month, sale_price=Decimal("130.00")))  # +300
    service.create_record(make_record(sale_date=date(2025, 6, 1), sale_price=Decimal("110.00")))  # +100

    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window.total_profit_value.text() == "+400.00 元"
    assert window.year_profit_value.text() == "+300.00 元"  # 2025 年不计入本年
    assert window.month_profit_value.text() == "+300.00 元"
    assert window.total_count_value.text() == "2 笔"


def test_stat_cards_unaffected_by_search_filter(service, qtbot):
    """STA-01：筛选某个月记录时，四张全局卡片保持全局值。"""
    today = date.today()
    this_month = today.replace(day=1)
    service.create_record(
        make_record(bond_name="本月转债", sale_date=this_month, sale_price=Decimal("130.00"))
    )  # +300
    service.create_record(make_record(sale_date=date(2025, 6, 1), sale_price=Decimal("110.00")))  # +100

    window = MainWindow(service)
    qtbot.addWidget(window)
    before = [
        window.total_profit_value.text(),
        window.year_profit_value.text(),
        window.month_profit_value.text(),
        window.total_count_value.text(),
    ]

    window.search_input.setText("本月")  # 只命中 2026 年那条
    window._on_search_changed()
    assert window.table.rowCount() == 1  # 列表被筛选

    after = [
        window.total_profit_value.text(),
        window.year_profit_value.text(),
        window.month_profit_value.text(),
        window.total_count_value.text(),
    ]
    assert before == after  # 卡片保持全局值


def test_stat_cards_refresh_after_delete(service, qtbot, monkeypatch):
    today = date.today()
    service.create_record(make_record(sale_date=today.replace(day=1)))
    window = MainWindow(service)
    qtbot.addWidget(window)
    assert window.total_count_value.text() == "1 笔"

    window.table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    window._on_delete()

    assert window.total_count_value.text() == "0 笔"
    assert window.total_profit_value.text() == "0.00 元"


def test_empty_state_shown_when_no_records(service, qtbot):
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window.stack.currentIndex() == 1  # 空状态页
    assert window.empty_title.text() == "还没有任何卖出记录"

    service.create_record(make_record())
    window.refresh_records()
    assert window.stack.currentIndex() == 0  # 有记录后回到表格页


def test_empty_state_add_button_opens_dialog(service, qtbot, monkeypatch):
    window = MainWindow(service)
    qtbot.addWidget(window)

    opened = {}
    record_arg = {}

    class FakeDialog:
        def __init__(self, svc, parent=None, record=None):
            opened["count"] = opened.get("count", 0) + 1
            record_arg["record"] = record

        def exec(self):
            return 1

    monkeypatch.setattr(main_window_module, "RecordDialog", FakeDialog)
    window.empty_add_button.click()
    assert opened["count"] == 1
    assert record_arg["record"] is None  # 空状态入口是新增，不是编辑
