"""备份与恢复页（阶段 4 / §6）：手动备份、备份列表、恢复所选、立即检查。

「手动备份 / 恢复 / 立即检查」按钮只发射信号，由主窗口在槽内调用备份服务——
页面不持有服务层对象（与 data_management 相同，避免循环引用导致的
对象生命周期问题，见批次 11 教训）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bond_profit.infrastructure.backup import BackupInfo
from bond_profit.ui import theme
from bond_profit.ui.tokens import SPACE_L, SPACE_XL

_COLUMNS = ("备份时间", "类型", "记录数", "数据库版本", "验证状态", "文件")
_KIND_LABELS = {"auto": "自动", "manual": "手动", "protected": "保护"}


class BackupPage(QWidget):
    """备份与恢复页。"""

    manual_backup_requested = Signal(str)  # 用户选择的保存目录
    restore_requested = Signal(str)  # 所选备份文件路径
    check_requested = Signal()  # 立即检查自动备份（含失败后的重试）
    refresh_requested = Signal()  # 仅重新读取备份列表

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._infos: list[BackupInfo] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_XL, SPACE_XL, SPACE_XL, SPACE_XL)
        layout.setSpacing(SPACE_L)

        # 阶段 6：标题/提示改 objectName + QSS（theme.py #pageTitle/#pageHint）
        title = QLabel("备份与恢复")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        hint = QLabel(
            "自动备份：数据变更后按天生成（每天最多一份，保留最近 30 份）。"
            "手动备份由你选择保存位置，建议存到其他磁盘；"
            "升级前与恢复前会自动创建保护备份，不参与自动清理。"
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        self.backup_now_button = QPushButton("手动备份到…")
        self.backup_now_button.setProperty("accent", True)  # 本页主操作
        self.backup_now_button.setToolTip("选择保存目录（建议其他磁盘），生成当前数据的完整备份")
        self.check_button = QPushButton("立即检查自动备份")
        self.check_button.setToolTip("启动检查或定时检查失败后，可用此按钮重试")
        self.refresh_button = QPushButton("刷新列表")
        for button in (self.backup_now_button, self.check_button, self.refresh_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)  # 阶段 6：与总览表格一致的斑马纹
        self.table.setMouseTracking(True)  # 阶段 6：行悬浮高亮
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        restore_row = QHBoxLayout()
        self.count_label = QLabel("")
        restore_row.addWidget(self.count_label)
        restore_row.addStretch()
        self.restore_button = QPushButton("恢复所选备份…")
        self.restore_button.setToolTip("用所选备份替换当前全部数据，替换前会自动创建保护备份")
        restore_row.addWidget(self.restore_button)
        layout.addLayout(restore_row)

        self.backup_now_button.clicked.connect(self._on_manual_backup)
        self.check_button.clicked.connect(self.check_requested.emit)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.restore_button.clicked.connect(self._on_restore)

    # ---- 数据显示 -----------------------------------------------------------

    def populate_backups(self, infos: list[BackupInfo]) -> None:
        """重建备份列表（最新在前由服务层保证）。"""
        self._infos = list(infos)
        self.table.setRowCount(len(self._infos))
        for row, info in enumerate(self._infos):
            kind = _KIND_LABELS.get(info.kind, "未知")
            verified = "通过" if info.verified else "未通过"
            values = (
                info.created_at,
                kind,
                str(info.record_count),
                str(info.schema_version),
                verified,
                info.path.name,
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if not info.verified:
                    item.setForeground(theme.error_color())
                self.table.setItem(row, col, item)
        self.count_label.setText(
            f"共 {len(self._infos)} 份备份（自动备份保留最近 30 份，"
            "保护/手动备份不自动清理）"
        )

    def _selected_path(self) -> str | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._infos):
            return str(self._infos[row].path)
        return None

    # ---- 动作（仅发信号，服务调用在主窗口） -----------------------------------

    def _on_manual_backup(self) -> None:
        dest = QFileDialog.getExistingDirectory(self, "选择手动备份保存目录")
        if dest:
            self.manual_backup_requested.emit(dest)

    def _on_restore(self) -> None:
        path = self._selected_path()
        if path is None:
            QMessageBox.information(self, "恢复备份", "请先在列表中选择一份备份。")
            return
        answer = QMessageBox.question(
            self,
            "恢复确认",
            "恢复将把当前数据库完整替换为所选备份的内容，\n"
            "备份之后新录入的数据会丢失。\n\n"
            "恢复前会自动为当前数据创建保护备份；过程失败时当前数据不受影响。\n\n"
            "确定继续恢复吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.restore_requested.emit(path)
