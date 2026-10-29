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
from bond_profit.ui.widgets import (
    Divider,
    GhostButton,
    MiniStat,
    PrimaryButton,
    set_flag,
)

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
        self.resize(900, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(0)

        title = QLabel("导入预览")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(Divider())
        layout.addSpacing(14)

        # ---- 统计条：每个数字一个 mini 指标（旧版挤成一句长文本） ----------
        stats = QHBoxLayout()
        stats.setSpacing(24)
        self.new_stat = MiniStat("预计新增")
        self.duplicate_stat = MiniStat("重复跳过")
        self.error_stat = MiniStat("错误")
        self.net_stat = MiniStat("净收益变化")
        self.new_stat.set_value(f"{preview.new_count} 笔")
        self.duplicate_stat.set_value(f"{preview.duplicate_count} 笔")
        self.error_stat.set_value(f"{preview.error_count} 笔")
        set_flag(self.error_stat.value, "danger", preview.error_count > 0)
        self.net_stat.set_value(
            format_money(preview.net_profit), sign=float(preview.net_profit)
        )
        for stat in (self.new_stat, self.duplicate_stat, self.error_stat, self.net_stat):
            stats.addWidget(stat)
        stats.addStretch()
        layout.addLayout(stats)
        layout.addSpacing(14)

        # ---- 状态芯片：能否导入一眼可见 -------------------------------------
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.status_chip = QLabel(
            "存在错误行，无法导入" if preview.has_errors else "全部行可导入"
        )
        self.status_chip.setObjectName("chip")
        set_flag(self.status_chip, "danger", preview.has_errors)
        chips.addWidget(self.status_chip)
        chips.addStretch()
        layout.addLayout(chips)
        layout.addSpacing(14)

        # 完整句子保留为隐藏控件：测试直接断言 summary_label.text()，不参与排版
        self.summary_label = QLabel(
            f"预计新增 {preview.new_count} 笔，重复跳过 "
            f"{preview.duplicate_count} 笔，错误 {preview.error_count} 笔，"
            f"预计净收益变化 {format_money(preview.net_profit)} 元"
        )
        self.summary_label.setVisible(False)

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
        self.error_hint.setObjectName("chip")
        set_flag(self.error_hint, "danger", True)
        self.error_hint.setVisible(preview.has_errors)
        layout.addWidget(self.error_hint)
        layout.addSpacing(12)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch()
        self.cancel_button = GhostButton("取消")
        self.confirm_button = PrimaryButton("开始导入")
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
