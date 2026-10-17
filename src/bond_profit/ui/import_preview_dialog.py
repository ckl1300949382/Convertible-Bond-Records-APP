"""导入预览对话框（§4.4）：逐行状态、统计与确认导入。

预览展示「可导入／重复跳过／错误」逐行状态与错误原因；
存在错误行时禁止导入；确认后单事务写入并展示实际结果。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from bond_profit.application.excel_service import (
    ExcelError,
    ExcelService,
    ImportPreview,
)
from bond_profit.domain.calculations import format_money

_COLUMNS = (
    "Excel 行号",
    "状态",
    "转债名称",
    "转债代码",
    "卖出日期",
    "卖出价格",
    "卖出数量",
    "备注",
    "说明",
)

_STATUS_TEXT = {"new": "可导入", "duplicate": "重复跳过", "error": "错误"}
_STATUS_COLOR = {
    "new": None,
    "duplicate": QColor(176, 122, 0),  # 琥珀色，提示跳过
    "error": QColor(200, 0, 0),
}
_DUPLICATE_HINT = "与数据库已有记录或文件内其他行相同"


class ImportPreviewDialog(QDialog):
    def __init__(
        self,
        excel_service: ExcelService,
        preview: ImportPreview,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._excel = excel_service
        self._preview = preview

        self.setWindowTitle("导入预览")
        self.resize(880, 560)

        layout = QVBoxLayout(self)

        self.summary_label = QLabel(
            f"预计新增 {preview.new_count} 笔，重复跳过 "
            f"{preview.duplicate_count} 笔，错误 {preview.error_count} 笔，"
            f"预计净收益变化 {format_money(preview.net_profit)} 元"
        )
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self._fill_rows()
        layout.addWidget(self.table)

        self.error_hint = QLabel("存在错误行，请修正源文件后重新导入")
        self.error_hint.setStyleSheet("color: rgb(200, 0, 0);")
        self.error_hint.setVisible(preview.has_errors)
        layout.addWidget(self.error_hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = QPushButton("取消")
        self.confirm_button = QPushButton("开始导入")
        if preview.has_errors:  # 任一错误整批不可提交（§4.3）
            self.confirm_button.setEnabled(False)
            self.confirm_button.setToolTip("存在错误行，无法导入")
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        layout.addLayout(buttons)

        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self._on_confirm)

    # ---- 显示 ---------------------------------------------------------------

    def _fill_rows(self) -> None:
        for row_result in self._preview.rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            record = row_result.record
            if row_result.status == "error":
                values = (
                    str(row_result.row_number),
                    _STATUS_TEXT["error"],
                    "", "", "", "", "", "",
                    row_result.reason,
                )
            else:
                values = (
                    str(row_result.row_number),
                    _STATUS_TEXT[row_result.status],
                    record.bond_name,
                    record.bond_code,
                    record.sale_date.isoformat(),
                    f"{record.sale_price:.2f}",
                    str(record.quantity),
                    record.note,
                    _DUPLICATE_HINT if row_result.status == "duplicate" else "",
                )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                color = _STATUS_COLOR[row_result.status]
                if color is not None:
                    item.setForeground(color)
                if col in (0, 1, 3, 4, 5, 6):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, col, item)

    # ---- 动作 -----------------------------------------------------------------

    def _on_confirm(self) -> None:
        try:
            result = self._excel.commit_import(self._preview)
        except Exception as exc:  # ExcelError / RepositoryError，信息面向用户
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        QMessageBox.information(
            self,
            "导入完成",
            f"实际新增 {result.added_count} 笔，跳过 {result.skipped_count} 笔，"
            f"净收益变化 {format_money(result.net_profit)} 元",
        )
        self.accept()
