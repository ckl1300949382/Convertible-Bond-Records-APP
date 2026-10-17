"""主窗口：交易记录管理。

阶段 1 提供记录表格与增删改；阶段 2 扩展统计卡片、搜索/筛选/排序/分页（§3.2/§3.3）。
图表由批次 7 加入。
"""

from __future__ import annotations

import bond_profit
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bond_profit.application.sales_service import SalesService
from bond_profit.domain.calculations import format_money, profit_per_record
from bond_profit.domain.models import RecordQuery, SaleRecord
from bond_profit.ui.record_dialog import RecordDialog

_COLUMNS = (
    "卖出日期",
    "转债名称",
    "转债代码",
    "卖出单价(元)",
    "卖出数量(张)",
    "单笔收益(元)",
    "备注",
)

# 表头列 → 排序键（§3.3 只允许按日期、价格、收益排序）
_SORTABLE_COLUMNS = {0: "date", 3: "price", 5: "profit"}
_PAGE_SIZE = 20  # 每页 20 条（§3.3）


class MainWindow(QMainWindow):
    def __init__(self, service: SalesService) -> None:
        super().__init__()
        self._service = service
        self._records: list[SaleRecord] = []
        self._page = 1
        self._total = 0
        self._sort_key = "date"
        self._sort_desc = True  # 默认最新日期在前（§3.3）

        self.setWindowTitle(f"可转债收益记录 v{bond_profit.__version__}")
        self.resize(1000, 640)

        central = QWidget()
        layout = QVBoxLayout(central)

        # ---- 顶部工具栏：动作按钮 + 搜索/筛选 --------------------------------
        toolbar = QHBoxLayout()
        self.add_button = QPushButton("新增记录")
        self.edit_button = QPushButton("编辑记录")
        self.delete_button = QPushButton("删除记录")
        for button in (self.add_button, self.edit_button, self.delete_button):
            toolbar.addWidget(button)
        toolbar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索名称或代码")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(200)
        self.search_input.setToolTip("按 Ctrl+F 快速聚焦")
        toolbar.addWidget(self.search_input)

        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(100)
        toolbar.addWidget(self.year_combo)

        self.month_combo = QComboBox()
        self.month_combo.setFixedWidth(90)
        self.month_combo.setEnabled(False)  # 选择具体年份后才可用
        self.month_combo.addItem("全部月份", None)
        for month in range(1, 13):
            self.month_combo.addItem(f"{month} 月", month)
        toolbar.addWidget(self.month_combo)

        layout.addLayout(toolbar)

        # ---- 统计卡片：全局值，不随列表搜索/筛选变化（§3.2，STA-01） ----------
        cards_row = QHBoxLayout()
        self.total_profit_value = self._make_stat_card(
            cards_row, "累计收益"
        )
        self.year_profit_value = self._make_stat_card(cards_row, "本年收益")
        self.month_profit_value = self._make_stat_card(cards_row, "本月收益")
        self.total_count_value = self._make_stat_card(
            cards_row, "累计卖出笔数"
        )
        layout.addLayout(cards_row)

        # ---- 页面栈：记录表格页 / 空状态页 ------------------------------------
        self.stack = QStackedWidget()

        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # ---- 记录表格 --------------------------------------------------------
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
        header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        table_layout.addWidget(self.table)

        # ---- 底部分页栏 --------------------------------------------------------
        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.prev_button = QPushButton("上一页")
        self.next_button = QPushButton("下一页")
        self.page_label = QLabel("")
        bottom.addWidget(self.prev_button)
        bottom.addWidget(self.page_label)
        bottom.addWidget(self.next_button)
        table_layout.addLayout(bottom)

        self.stack.addWidget(table_page)

        # ---- 空状态页（§3.2：清晰空状态 + 新增入口，不插入示例数据） -----------
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.addStretch()
        self.empty_title = QLabel("还没有任何卖出记录")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.empty_add_button = QPushButton("新增第一条记录")
        button_row.addWidget(self.empty_add_button)
        button_row.addStretch()
        empty_layout.addLayout(button_row)
        empty_layout.addStretch()
        self.stack.addWidget(empty_page)

        layout.addWidget(self.stack)

        self.setCentralWidget(central)

        # ---- 信号 -------------------------------------------------------------
        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        self.table.doubleClicked.connect(self._on_edit)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.search_input.textEdited.connect(self._on_search_changed)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        self.prev_button.clicked.connect(self._on_prev_page)
        self.next_button.clicked.connect(self._on_next_page)
        self.empty_add_button.clicked.connect(self._on_add)

        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._on_focus_search)

        self.refresh_records()

    # ---- 数据显示 ----------------------------------------------------------

    def refresh_records(self) -> None:
        """按当前搜索/筛选/排序/页码从服务层读取并重建表格与统计卡片。

        卡片为全局值（全量聚合，STA-01）；图表刷新在批次 7 接入同一入口。
        """
        self._sync_year_options()
        query = self._build_query()
        result = self._service.list_page(query, self._page, _PAGE_SIZE)
        self._records = result.records
        self._total = result.total
        self._page = result.page  # 页码钳制（删除当前页最后一条时自动前移）

        self._refresh_stat_cards()
        self.stack.setCurrentIndex(1 if self._total == 0 else 0)

        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
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

        last_page = max(1, -(-self._total // _PAGE_SIZE))
        self.count_label.setText(f"共 {self._total} 条记录")
        self.page_label.setText(f"第 {self._page} / {last_page} 页")
        self.prev_button.setEnabled(self._page > 1)
        self.next_button.setEnabled(self._page < last_page)

    def _make_stat_card(self, row: QHBoxLayout, title: str) -> QLabel:
        """构建一张统计卡片，返回值标签（§3.2）。"""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        box = QVBoxLayout(frame)
        title_label = QLabel(title)
        value_label = QLabel("0.00")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title_label)
        box.addWidget(value_label)
        row.addWidget(frame, stretch=1)
        return value_label

    def _refresh_stat_cards(self) -> None:
        """刷新四张全局统计卡片（§3.2），显示带正负号与单位。"""
        stats = self._service.global_statistics()
        self.total_profit_value.setText(f"{format_money(stats.total_profit)} 元")
        self.year_profit_value.setText(f"{format_money(stats.year_profit)} 元")
        self.month_profit_value.setText(f"{format_money(stats.month_profit)} 元")
        self.total_count_value.setText(f"{stats.total_count} 笔")

    def _selected_record(self) -> SaleRecord | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    # ---- 搜索 / 筛选 / 排序 / 分页 ------------------------------------------

    def _build_query(self) -> RecordQuery:
        return RecordQuery(
            keyword=self.search_input.text().strip(),
            year=self.year_combo.currentData(),
            month=self.month_combo.currentData(),
            sort_key=self._sort_key,
            descending=self._sort_desc,
        )

    def _sync_year_options(self) -> None:
        """按数据库中实际出现的年份刷新下拉，保留当前选择。

        信号在重建期间屏蔽，选择失效（该年记录全删）时重置并回第一页。
        """
        years = self._service.distinct_years()
        current = self.year_combo.currentData()
        options = [None, *years]
        values = [self.year_combo.itemData(i) for i in range(self.year_combo.count())]
        if values == options:
            return
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem("全部年份", None)
        for year in years:
            self.year_combo.addItem(f"{year} 年", year)
        if current is not None and current in years:
            index = self.year_combo.findData(current)
            self.year_combo.setCurrentIndex(index)
        elif current is not None:
            # 原选年份已无记录，重置筛选
            self.month_combo.blockSignals(True)
            self.month_combo.setCurrentIndex(0)
            self.month_combo.blockSignals(False)
            self.month_combo.setEnabled(False)
            self._page = 1
        self.year_combo.blockSignals(False)

    def _on_search_changed(self) -> None:
        self._page = 1  # 筛选变更后回到第一页（§3.3）
        self.refresh_records()

    def _on_year_changed(self) -> None:
        has_year = self.year_combo.currentData() is not None
        self.month_combo.setEnabled(has_year)
        if not has_year:
            self.month_combo.blockSignals(True)
            self.month_combo.setCurrentIndex(0)
            self.month_combo.blockSignals(False)
        self._page = 1
        self.refresh_records()

    def _on_month_changed(self) -> None:
        self._page = 1
        self.refresh_records()

    def _on_header_clicked(self, section: int) -> None:
        sort_key = _SORTABLE_COLUMNS.get(section)
        if sort_key is None:
            return
        if sort_key == self._sort_key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = sort_key
            self._sort_desc = True
        order = (
            Qt.SortOrder.DescendingOrder
            if self._sort_desc
            else Qt.SortOrder.AscendingOrder
        )
        self.table.horizontalHeader().setSortIndicator(section, order)
        self._page = 1
        self.refresh_records()

    def _on_prev_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self.refresh_records()

    def _on_next_page(self) -> None:
        last_page = max(1, -(-self._total // _PAGE_SIZE))
        if self._page < last_page:
            self._page += 1
            self.refresh_records()

    def _on_focus_search(self) -> None:
        self.search_input.setFocus()
        self.search_input.selectAll()

    # ---- 动作 ---------------------------------------------------------------

    def _on_add(self) -> None:
        dialog = RecordDialog(self._service, parent=self)
        if dialog.exec():
            self.refresh_records()

    def _on_edit(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        dialog = RecordDialog(self._service, record=record, parent=self)
        if dialog.exec():
            self.refresh_records()

    def _on_delete(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        answer = QMessageBox.question(
            self,
            "删除确认",
            f"确定删除「{record.bond_name}」"
            f"（{record.sale_date.isoformat()}）这条记录吗？删除后不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_record(record.id)
        except Exception as exc:  # RepositoryError 等数据库异常
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        self.refresh_records()
