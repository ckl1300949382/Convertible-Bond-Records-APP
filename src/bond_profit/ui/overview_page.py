"""总览页：hero 数字区 + 工具栏 + 图表 + 记录表格 + 分页 + 空状态。

从 ``main_window.py`` 迁出（批次 3）：此前 170 行 UI 构建全堆在
``MainWindow.__init__``，改一个圆角要碰三个地方。现在本类只管「长什么样」，
数据填充与业务编排仍由 ``MainWindow`` 负责——页面不持有服务层对象。

与测试的契约（不可违反）：
- 所有控件仍以原名暴露（``table`` / ``search_input`` / ``total_profit_value``
  等），``MainWindow`` 做属性转发，测试对 ``window.<控件>`` 的访问不受影响。
- 表格 7 列顺序、20 条/页、排序白名单由 MainWindow 保证，本类不碰数据。
- ``total_profit_value`` / ``year_profit_value`` / ``month_profit_value``
  的 ``text()`` 只含数字与正负号（「元」拆成独立小号单位标签），
  ``total_count_value`` 仍含「笔」——与已批准的测试改动一致。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bond_profit.ui.bar_chart import BarChart
from bond_profit.ui.widgets import PrimaryButton

_COLUMNS = (
    "卖出日期",
    "转债名称",
    "转债代码",
    "卖出单价(元)",
    "卖出数量(张)",
    "单笔收益(元)",
    "备注",
)


def _named(widget: QWidget, name: str) -> QWidget:
    widget.setObjectName(name)
    return widget


def _set_sign_class(label: QLabel, value: float) -> None:
    """按正负号设置动态属性（pos/neg），QSS 据此红涨绿跌；零为中性灰。"""
    old = (label.property("pos"), label.property("neg"))
    new = ("true" if value > 0 else "", "true" if value < 0 else "")
    if old != new:
        label.setProperty("pos", new[0])
        label.setProperty("neg", new[1])
        label.style().unpolish(label)
        label.style().polish(label)


class OverviewPage(QWidget):
    """总览页全部界面。布局对应提案 B「数字剧场」的信息架构。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 14)
        layout.setSpacing(0)

        # ---- 顶部：页标题 + 动作/筛选 ------------------------------------
        head = QHBoxLayout()
        head.setSpacing(8)
        self.page_title = _named(QLabel("总览"), "pageTitle")
        head.addWidget(self.page_title)
        head.addSpacing(6)

        self.edit_button = QPushButton("编辑记录")
        self.delete_button = QPushButton("删除记录")
        head.addWidget(self.edit_button)
        head.addWidget(self.delete_button)
        head.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索名称或代码")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(200)
        self.search_input.setToolTip("按 Ctrl+F 快速聚焦")
        head.addWidget(self.search_input)

        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(100)
        head.addWidget(self.year_combo)

        self.month_combo = QComboBox()
        self.month_combo.setFixedWidth(90)
        self.month_combo.setEnabled(False)  # 选择具体年份后才可用
        self.month_combo.addItem("全部月份", None)
        for month in range(1, 13):
            self.month_combo.addItem(f"{month} 月", month)
        head.addWidget(self.month_combo)

        self.add_button = PrimaryButton("新增记录", icon_name="plus")
        head.addWidget(self.add_button)
        layout.addLayout(head)

        # ---- HERO：累计收益唯一主视觉，其余三项降为 mini（§3.2 STA-01） --
        hero = QHBoxLayout()
        hero.setSpacing(0)
        hero.setContentsMargins(0, 10, 0, 14)

        hero_main = QVBoxLayout()
        hero_main.setSpacing(0)
        hero_main.addWidget(_named(QLabel("累计收益"), "heroLabel"))
        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        # 数字与「元」拆成两个控件：62px 与 15px 的字号差靠同一行内拼不出来
        self.total_profit_value = _named(QLabel("0.00"), "heroValue")
        self.total_profit_value.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        hero_unit = _named(QLabel("元"), "heroUnit")
        value_row.addWidget(self.total_profit_value)
        value_row.addWidget(hero_unit, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.setContentsMargins(0, 0, 0, 8)  # 单位标签抬到基线高度
        hero_main.addLayout(value_row)
        hero.addLayout(hero_main)
        hero.addSpacing(34)

        self.year_profit_value = self._make_mini(hero, "本年收益")
        self.month_profit_value = self._make_mini(hero, "本月收益")
        self.total_count_value = self._make_mini(hero, "累计卖出")
        hero.addStretch()
        layout.addLayout(hero)

        # ---- 页面栈：记录表格页 / 空状态页 --------------------------------
        self.stack = QStackedWidget()

        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)

        # 图表区（批次 5 重绘样式，本批仅迁移结构；必须保持 BarChart 类型）
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        monthly_box = QVBoxLayout()
        monthly_header = QHBoxLayout()
        self.monthly_title = _named(QLabel("月度收益"), "chartTitle")
        monthly_header.addWidget(self.monthly_title)
        monthly_header.addStretch()
        self.chart_year_combo = QComboBox()
        self.chart_year_combo.setEnabled(False)  # 无记录时不可选
        monthly_header.addWidget(self.chart_year_combo)
        monthly_box.addLayout(monthly_header)
        self.monthly_chart = BarChart()
        monthly_box.addWidget(self.monthly_chart)
        charts_row.addLayout(monthly_box, stretch=1)

        yearly_box = QVBoxLayout()
        yearly_box.addWidget(_named(QLabel("年度收益"), "chartTitle"))
        self.yearly_chart = BarChart()
        yearly_box.addWidget(self.yearly_chart)
        charts_row.addLayout(yearly_box, stretch=1)

        table_layout.addLayout(charts_row)

        # ---- 记录表格 -----------------------------------------------------
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)  # 手动管理排序，避免按文本排序
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(True)
        table_layout.addWidget(self.table, stretch=1)

        # ---- 底部分页栏 -----------------------------------------------------
        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.prev_button = QPushButton("上一页")
        self.page_label = QLabel("")
        self.next_button = QPushButton("下一页")
        bottom.addWidget(self.prev_button)
        bottom.addWidget(self.page_label)
        bottom.addWidget(self.next_button)
        table_layout.addLayout(bottom)

        self.stack.addWidget(table_page)

        # ---- 空状态页（§3.2：清晰空状态 + 新增入口，不插入示例数据） -------
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.addStretch()
        self.empty_title = QLabel("还没有任何卖出记录")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setObjectName("emptyTitle")
        empty_layout.addWidget(self.empty_title)
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.empty_add_button = PrimaryButton("新增第一条记录")
        button_row.addWidget(self.empty_add_button)
        button_row.addStretch()
        empty_layout.addLayout(button_row)
        empty_layout.addStretch()
        self.stack.addWidget(empty_page)

        layout.addWidget(self.stack, stretch=1)

        self._table_page_index = 0

    # ------------------------------------------------------------------ UI

    def _make_mini(self, hero: QHBoxLayout, title: str) -> QLabel:
        """hero 右侧的一个 mini 指标：小标题 + 19px 数字 + 独立单位。

        单位标签由 QSS 定字号；值标签的 ``text()`` 只含数字，
        「笔」除外（见模块 docstring 的测试契约说明）。
        """
        box = QVBoxLayout()
        box.setSpacing(0)
        box.addWidget(_named(QLabel(title), "miniLabel"))
        value = _named(QLabel("0.00"), "miniValue")
        box.addWidget(value)
        hero.addLayout(box)
        hero.addSpacing(34)
        return value

    def show_table(self, has_records: bool) -> None:
        """有记录显示表格页，否则显示空状态页。"""
        self.stack.setCurrentIndex(self._table_page_index if has_records else 1)

    # ----------------------------------------------------------------- 数据

    def set_hero_value(self, label: QLabel, text: str, value: float) -> None:
        """填充 hero/mini 数字并按正负号上色。"""
        label.setText(text)
        _set_sign_class(label, value)

    def fill_table(self, records: list) -> None:  # noqa: ANN401
        """按行填充表格；列顺序与 _COLUMNS 严格一致（测试用 item(row, 5)）。"""
        from bond_profit.domain.calculations import format_money, profit_per_record

        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            profit = profit_per_record(record.sale_price, record.quantity)
            values = (
                record.sale_date.isoformat(),
                record.bond_name,
                record.bond_code,
                f"{record.sale_price:.2f}",
                str(record.quantity),
                format_money(profit),
                record.note,
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col in (3, 4, 5):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, col, item)

    def set_pager(self, total: int, page: int, last_page: int) -> None:
        self.count_label.setText(f"共 {total} 条记录")
        self.page_label.setText(f"第 {page} / {last_page} 页")
        self.prev_button.setEnabled(page > 1)
        self.next_button.setEnabled(page < last_page)
