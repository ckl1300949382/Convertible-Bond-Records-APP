"""主窗口：交易记录管理（阶段 1 范围）。

阶段 2 将扩展统计卡片、搜索筛选排序分页与图表。
"""

from __future__ import annotations

import bond_profit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bond_profit.application.sales_service import SalesService
from bond_profit.domain.calculations import format_money, profit_per_record
from bond_profit.domain.models import SaleRecord
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


class MainWindow(QMainWindow):
    def __init__(self, service: SalesService) -> None:
        super().__init__()
        self._service = service
        self._records: list[SaleRecord] = []

        self.setWindowTitle(f"可转债收益记录 v{bond_profit.__version__}")
        self.resize(1000, 640)

        central = QWidget()
        layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.add_button = QPushButton("新增记录")
        self.edit_button = QPushButton("编辑记录")
        self.delete_button = QPushButton("删除记录")
        for button in (self.add_button, self.edit_button, self.delete_button):
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.table)

        self.count_label = QLabel("")
        layout.addWidget(self.count_label)
        self.setCentralWidget(central)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.delete_button.clicked.connect(self._on_delete)
        self.table.doubleClicked.connect(self._on_edit)

        self.refresh_records()

    # ---- 数据显示 ----------------------------------------------------------

    def refresh_records(self) -> None:
        """从服务层读取全部记录并重建表格（§3.3 默认次序）。"""
        self._records = self._service.list_records()
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
        self.count_label.setText(f"共 {len(self._records)} 条记录")

    def _selected_record(self) -> SaleRecord | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

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
