"""主窗口测试：表格显示、删除确认（REC-03）、刷新联动、统计卡片与空状态。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMessageBox

import bond_profit.ui.main_window as main_window_module
from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.domain.models import SaleRecord
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui import prefs, theme
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
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    assert window.table.rowCount() == 0
    assert window.count_label.text() == "共 0 条记录"


def test_refresh_shows_records_with_profit(service, qtbot):
    service.create_record(make_record())
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "平银转债"
    assert window.table.item(0, 5).text() == "+300.00"  # (130-100)*10
    assert window.count_label.text() == "共 1 条记录"


def test_delete_cancelled_keeps_record(service, qtbot, monkeypatch):
    service.create_record(make_record())
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)
    window.table.selectRow(0)

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    window._on_delete()

    assert window.table.rowCount() == 1


def test_delete_confirmed_removes_record(service, qtbot, monkeypatch):
    service.create_record(make_record())
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    assert window.table.rowCount() == 20
    assert window.page_label.text() == "第 1 / 2 页"
    assert window.count_label.text() == "共 25 条记录"
    assert not window.prev_button.isEnabled()
    assert window.next_button.isEnabled()


def test_pagination_next_and_prev(service, qtbot):
    seed_many(service)
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    window.search_input.setText("转债05")
    window._on_search_changed()
    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "转债05号"


def test_search_no_match_shows_empty(service, qtbot):
    seed_many(service)
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    window.search_input.setText("不存在的名称")
    window._on_search_changed()
    assert window.table.rowCount() == 0
    assert window.page_label.text() == "第 1 / 1 页"


def test_year_filter_and_month_combo_state(service, qtbot):
    service.create_record(make_record(sale_date=date(2026, 1, 15)))
    service.create_record(make_record(sale_date=date(2025, 6, 1)))
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    window._on_header_clicked(3)  # 卖出单价降序
    assert window.table.item(0, 1).text() == "高"

    window._on_header_clicked(3)  # 再点一次 → 升序
    assert window.table.item(0, 1).text() == "低"


def test_header_click_non_sortable_column_ignored(service, qtbot):
    seed_many(service, 3)
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    window._on_header_clicked(1)  # 名称列不允许排序，保持默认日期降序
    assert window._sort_key == "date"
    assert window._sort_desc is True


def test_delete_last_item_on_last_page_adjusts_page(service, qtbot, monkeypatch):
    seed_many(service, 21)  # 两页：20 + 1
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
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

    window = MainWindow(service, ExcelService(service))
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

    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
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
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    assert window.stack.currentIndex() == 1  # 空状态页
    assert window.empty_title.text() == "还没有任何卖出记录"

    service.create_record(make_record())
    window.refresh_records()
    assert window.stack.currentIndex() == 0  # 有记录后回到表格页


def test_empty_state_add_button_opens_dialog(service, qtbot, monkeypatch):
    window = MainWindow(service, ExcelService(service))
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


# ---- 阶段 2 批次 7：图表（§3.5，STA-02 / STA-03） -----------------------------


def test_charts_reflect_data_on_construction(service, qtbot):
    service.create_record(
        make_record(sale_date=date(2026, 3, 1), sale_price=Decimal("130.00"))
    )  # +300
    service.create_record(
        make_record(sale_date=date(2025, 6, 1), sale_price=Decimal("98.50"))
    )  # −15
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    # 月度图固定 12 项，默认显示最新年份 2026，缺失月份为 0（STA-02）
    monthly = window.monthly_chart.items
    assert len(monthly) == 12
    assert monthly[2] == ("3 月", Decimal("300.00"))
    assert monthly[0] == ("1 月", Decimal("0"))
    assert window.chart_year_combo.currentData() == 2026

    # 年度图年份升序，负收益保留（STA-03）
    assert window.yearly_chart.items == [
        ("2025", Decimal("-15.00")),
        ("2026", Decimal("300.00")),
    ]


def test_chart_year_combo_switch_updates_monthly_only(service, qtbot):
    service.create_record(make_record(sale_date=date(2026, 3, 1)))
    service.create_record(make_record(sale_date=date(2025, 6, 1)))
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    window.chart_year_combo.setCurrentIndex(window.chart_year_combo.findData(2025))
    monthly = window.monthly_chart.items
    assert monthly[5] == ("6 月", Decimal("300.00"))
    assert all(
        value == Decimal("0")
        for index, (_, value) in enumerate(monthly)
        if index != 5
    )

    assert window.table.rowCount() == 2  # 表格不受图表年份下拉影响


def test_charts_refresh_after_add_and_delete(service, qtbot, monkeypatch):
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)
    assert window.yearly_chart.items == []
    assert not window.chart_year_combo.isEnabled()  # 无记录时年份下拉不可选

    service.create_record(make_record(sale_date=date(2026, 3, 1)))
    window.refresh_records()
    assert window.yearly_chart.items == [("2026", Decimal("300.00"))]
    assert window.chart_year_combo.isEnabled()

    window.table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    window._on_delete()
    assert window.yearly_chart.items == []  # 删除后图表同步清空


# ---- 阶段 2 批次 8：主题 / 默认窗口与排序 / Ctrl+N（§3.6） --------------------


def test_theme_toggle_switches_and_saves(service, qtbot, qapp, tmp_path):
    ini = str(tmp_path / "prefs.ini")
    window = MainWindow(service, ExcelService(service), settings_path=ini)
    qtbot.addWidget(window)

    try:
        before = window.theme_button.text()
        window.theme_button.click()
        after = window.theme_button.text()
        assert {before, after} == {"浅色", "深色"}
        # 两套主题都有 QSS，用「实际样式表 == 该主题应有样式表」判断，而非「是否为空」
        expected_mode = "dark" if after == "深色" else "light"
        assert qapp.styleSheet() == theme.stylesheet_for(expected_mode)

        saved = prefs.open_settings(ini)
        assert saved.value("ui/theme") == ("dark" if after == "深色" else "light")
    finally:
        qapp.setStyleSheet("")  # 全局样式不泄漏到其他测试


def test_theme_restored_from_settings(service, qtbot, qapp, tmp_path, monkeypatch):
    ini = str(tmp_path / "prefs.ini")
    settings = prefs.open_settings(ini)
    prefs.save_theme(settings, "dark")

    window = MainWindow(service, ExcelService(service), settings_path=ini)
    qtbot.addWidget(window)
    try:
        assert window.theme_button.text() == "深色"
        assert "QTableWidget" in qapp.styleSheet()
    finally:
        qapp.setStyleSheet("")


def test_ctrl_n_opens_add_dialog(service, qtbot, monkeypatch):
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    ctrl_n = [
        s for s in window.findChildren(QShortcut) if s.key() == QKeySequence("Ctrl+N")
    ]
    assert len(ctrl_n) == 1

    opened = {}

    class FakeDialog:
        def __init__(self, svc, parent=None, record=None):
            opened["record"] = record

        def exec(self):
            return 1

    monkeypatch.setattr(main_window_module, "RecordDialog", FakeDialog)
    ctrl_n[0].activated.emit()
    assert opened["record"] is None  # Ctrl+N 是新增不是编辑


def test_window_geometry_and_sort_not_remembered(service, qtbot, tmp_path):
    """2026-10-29 起窗口尺寸与排序不持久化：重开后回到默认，筛选同样不记忆。"""
    ini = str(tmp_path / "prefs.ini")
    window = MainWindow(service, ExcelService(service), settings_path=ini)
    qtbot.addWidget(window)
    service.create_record(make_record())
    window.refresh_records()

    window.search_input.setText("不会保存的筛选")
    window._on_header_clicked(3)  # 临时改为价格降序
    window.resize(1150, 700)
    window.close()

    restored = MainWindow(service, ExcelService(service), settings_path=ini)
    qtbot.addWidget(restored)
    assert restored._sort_key == "date"  # 排序不记忆，回到默认
    assert restored._sort_desc is True
    assert restored.width() == 1080  # 窗口尺寸不记忆，回到默认
    assert restored.search_input.text() == ""  # 明确不记住筛选


# ---- 左侧导航与数据管理页（批次 10） -------------------------------------------

def test_nav_defaults_to_overview(service, qtbot):
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    assert window.nav_list.currentRow() == 0
    assert window.pages.currentIndex() == 0


def test_nav_switches_to_data_management(service, qtbot, monkeypatch):
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)

    window.nav_list.setCurrentRow(1)
    assert window.pages.currentIndex() == 1
    assert window.pages.currentWidget() is window.data_page

    # 筛选导出接线：信号 → 槽以当前查询条件调 run_export
    queries = []
    monkeypatch.setattr(
        window.data_page, "run_export", lambda q: queries.append(q)
    )
    window.data_page.export_filtered_requested.emit()
    assert queries == [window._build_query()]

    window.nav_list.setCurrentRow(0)
    assert window.pages.currentIndex() == 0


def test_import_completed_signal_refreshes_overview(service, qtbot):
    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)
    assert window.count_label.text() == "共 0 条记录"

    service.create_record(make_record())
    window.data_page.import_completed.emit()  # 模拟导入完成回调

    assert window.count_label.text() == "共 1 条记录"


# ---- 日志入口（阶段 5 日志复制） ------------------------------------------------

def test_open_logs_opens_log_folder(service, qtbot, tmp_path, monkeypatch):
    tmp_path.mkdir(exist_ok=True)
    monkeypatch.setattr(
        main_window_module, "current_log_dir", lambda: tmp_path
    )
    opened = []
    monkeypatch.setattr(
        main_window_module.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url)),
    )

    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)
    window.log_button.click()

    assert len(opened) == 1
    assert Path(opened[0].toLocalFile()) == tmp_path


def test_open_logs_without_log_dir_shows_hint(service, qtbot, monkeypatch):
    monkeypatch.setattr(main_window_module, "current_log_dir", lambda: None)
    hints = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: hints.append(a)),
    )

    window = MainWindow(service, ExcelService(service))
    qtbot.addWidget(window)
    window.log_button.click()  # 无日志目录：不崩溃，仅提示

    assert len(hints) == 1
    assert "尚未生成日志" in hints[0][2]
