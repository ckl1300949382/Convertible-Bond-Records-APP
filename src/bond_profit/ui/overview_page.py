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

from bond_profit.ui import icons, tokens
from bond_profit.ui.bar_chart import BarChart
from bond_profit.ui.widgets import (
    IconButton,
    PrimaryButton,
    RowHairlineDelegate,
    Segmented,
    apply_sign_property,
    current_mode,
)

_COLUMNS = (
    "卖出日期",
    "转债名称",
    "转债代码",
    "卖出单价(元)",
    "卖出数量(张)",
    "单笔收益(元)",
    "备注",
)

# 固定列宽（提案 B）：日期 94 / 名称 1fr / 代码 84 / 单价 92 / 数量 76 / 收益 100 / 备注 1fr。
# 旧版 ResizeToContents 会让列宽随内容跳变，翻页时整行左右抖动。
_FIXED_WIDTHS = {0: 94, 2: 84, 3: 92, 4: 76, 5: 100}


def _named(widget: QWidget, name: str) -> QWidget:
    widget.setObjectName(name)
    return widget


def _set_sign_class(label: QLabel, value: float) -> None:
    """按正负号设置动态属性（pos/neg），QSS 据此红涨绿跌；零为中性灰。"""
    apply_sign_property(label, value)


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

        # 图表区（批次 5）：月度/年度分段切换；两个 BarChart 都是真控件，
        # 数据始终同步刷新（测试同时断言两者 items），只是视觉上一次显示一个
        self.chart_segmented = Segmented(["月度收益", "年度收益"])
        self.chart_year_combo = QComboBox()
        self.chart_year_combo.setEnabled(False)  # 无记录时不可选
        self.chart_year_combo.setToolTip("月度图按年份查看")

        chart_head = QHBoxLayout()
        chart_head.setSpacing(8)
        chart_head.addWidget(self.chart_segmented)
        chart_head.addStretch()
        chart_head.addWidget(self.chart_year_combo)

        self.monthly_chart = BarChart()
        self.yearly_chart = BarChart()
        self.chart_stack = QStackedWidget()
        self.chart_stack.addWidget(self.monthly_chart)
        self.chart_stack.addWidget(self.yearly_chart)

        chart_area = QVBoxLayout()
        chart_area.setSpacing(6)
        chart_area.addLayout(chart_head)
        chart_area.addWidget(self.chart_stack)
        table_layout.addLayout(chart_area)

        self.chart_segmented.currentChanged.connect(self._on_chart_mode_changed)

        # ---- 记录表格 -----------------------------------------------------
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)  # 手动管理排序，避免按文本排序
        self.table.setShowGrid(False)  # 网格线换成行间发丝线（delegate 绘制）
        self.table.setMouseTracking(True)  # 不按下也跟踪悬停，行 hover 高亮才生效
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setItemDelegate(RowHairlineDelegate(self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(tokens.ROW_HEIGHT)

        header = self.table.horizontalHeader()
        header.setFixedHeight(tokens.HEADER_HEIGHT)
        header.setSortIndicatorShown(True)
        # 固定宽度列 + 两列 stretch（名称/备注）均分剩余空间
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for section, width in _FIXED_WIDTHS.items():
            header.setSectionResizeMode(section, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(section, width)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        table_layout.addWidget(self.table, stretch=1)

        # ---- 底部分页栏（tfoot：顶部发丝线 + 轻量胶囊分页） ----------------
        tfoot = QWidget()
        _named(tfoot, "tfoot")
        bottom = QHBoxLayout(tfoot)
        bottom.setContentsMargins(0, 0, 0, 0)
        self.count_label = _named(QLabel(""), "footMeta")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        # 文本契约：page_label 保持「第 N / M 页」（测试断言依赖该格式）
        self.page_label = _named(QLabel(""), "footMeta")
        self.prev_button = IconButton("chev-left", tooltip="上一页")
        self.next_button = IconButton("chev-right", tooltip="下一页")
        bottom.addWidget(self.prev_button)
        bottom.addWidget(self.page_label)
        bottom.addWidget(self.next_button)
        table_layout.addWidget(tfoot)

        self.stack.addWidget(table_page)

        # ---- 空状态页（§3.2：图形引导 + 主操作，不插入示例数据） -----------
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.addStretch()

        empty_col = QVBoxLayout()
        empty_col.setSpacing(12)
        empty_col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # 46px 圆角底 + 22px 线性图标（提案 B 的空状态视觉锚点）
        self._empty_icon_holder = _named(QLabel(), "emptyIcon")
        self._empty_icon_holder.setFixedSize(46, 46)
        self._empty_icon_holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_col.addWidget(
            self._empty_icon_holder, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        self.empty_title = QLabel("还没有任何卖出记录")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setObjectName("emptyTitle")
        empty_col.addWidget(self.empty_title)

        self.empty_sub = QLabel("新增第一条后，这里会自动算出收益与走势")
        self.empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_sub.setObjectName("emptySub")
        empty_col.addWidget(self.empty_sub)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.empty_add_button = PrimaryButton("新增第一条记录", icon_name="plus")
        button_row.addWidget(self.empty_add_button)
        button_row.addStretch()
        empty_col.addLayout(button_row)

        empty_layout.addLayout(empty_col)
        empty_layout.addStretch()
        self.stack.addWidget(empty_page)

        layout.addWidget(self.stack, stretch=1)

        self._table_page_index = 0
        self.refresh_theme()  # 初始空状态图标着色

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

    def refresh_theme(self) -> None:
        """主题切换后重取图标颜色（空状态图标是预渲染位图，QSS 管不到）。"""
        palette = tokens.palette_for(current_mode())
        self._empty_icon_holder.setPixmap(
            icons.pixmap("data", palette.text_3, size=22)
        )

    def show_table(self, has_records: bool) -> None:
        """有记录显示表格页，否则显示空状态页。"""
        self.stack.setCurrentIndex(self._table_page_index if has_records else 1)

    def _on_chart_mode_changed(self, index: int) -> None:
        """月度/年度分段切换；年份下拉只对月度图有意义。"""
        self.chart_stack.setCurrentIndex(index)
        self.chart_year_combo.setVisible(index == 0)

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
