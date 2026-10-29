"""备份与恢复页（阶段 4 / §6）：手动备份、备份列表、恢复所选、立即检查。

「手动备份 / 恢复 / 立即检查」按钮只发射信号，由主窗口在槽内调用备份服务——
页面不持有服务层对象（与 data_management 相同，避免循环引用导致的
对象生命周期问题，见批次 11 教训）。

视觉（批次 6）：与总览页同一套令牌——发丝线分组、StatusDot 显示备份健康度、
表格固定列宽 + 行间发丝线；「恢复」是破坏性操作，降权为危险色描边的次要按钮，
不与「手动备份」抢主操作位置。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bond_profit.infrastructure.backup import BackupInfo
from bond_profit.ui import tokens
from bond_profit.ui.widgets import (
    Divider,
    GhostButton,
    PrimaryButton,
    RowHairlineDelegate,
    StatusDot,
    current_mode,
)

_COLUMNS = ("备份时间", "类型", "记录数", "数据库版本", "验证状态", "文件")
_KIND_LABELS = {"auto": "自动", "manual": "手动", "protected": "保护"}

# 固定列宽：时间 150 / 类型 70 / 记录数 74 / 版本 96 / 状态 84 / 文件 1fr
# （旧版 ResizeToContents 会让列宽随文件名长短跳变）
_FIXED_WIDTHS = {0: 150, 1: 70, 2: 74, 3: 96, 4: 84}


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
        layout.setContentsMargins(24, 16, 24, 14)
        layout.setSpacing(0)

        # ---- 页标题 + 说明 --------------------------------------------------
        title = QLabel("备份与恢复")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(Divider())
        layout.addSpacing(16)

        hint = QLabel(
            "自动备份：数据变更后按天生成（每天最多一份，保留最近 30 份）。"
            "手动备份由你选择保存位置，建议存到其他磁盘；"
            "升级前与恢复前会自动创建保护备份，不参与自动清理。"
        )
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(14)

        # ---- 备份健康度：StatusDot + 一句话状态 ------------------------------
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_dot = StatusDot(ok=False)
        self.status_label = QLabel("尚未读取备份")
        self.status_label.setObjectName("statusLine")
        status_row.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        layout.addLayout(status_row)
        layout.addSpacing(14)

        # ---- 操作区：手动备份为主操作，检查/刷新为次要 ------------------------
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.backup_now_button = PrimaryButton("手动备份到…")
        self.backup_now_button.setToolTip(
            "选择保存目录（建议其他磁盘），生成当前数据的完整备份"
        )
        self.check_button = GhostButton("立即检查自动备份")
        self.check_button.setToolTip("启动检查或定时检查失败后，可用此按钮重试")
        self.refresh_button = GhostButton("刷新列表")
        for button in (self.backup_now_button, self.check_button, self.refresh_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addSpacing(16)

        # ---- 备份列表（与总览页表格同一套视觉） ------------------------------
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setItemDelegate(RowHairlineDelegate(self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(tokens.ROW_HEIGHT)

        header = self.table.horizontalHeader()
        header.setFixedHeight(tokens.HEADER_HEIGHT)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for section, width in _FIXED_WIDTHS.items():
            header.setSectionResizeMode(section, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(section, width)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        # ---- 底栏：份数 + 降权的危险操作 -------------------------------------
        tfoot = QWidget()
        tfoot.setObjectName("tfoot")
        bottom = QHBoxLayout(tfoot)
        bottom.setContentsMargins(0, 0, 0, 0)
        self.count_label = QLabel("")
        self.count_label.setObjectName("footMeta")
        bottom.addWidget(self.count_label)
        bottom.addStretch()
        self.restore_button = GhostButton("恢复所选备份…")
        self.restore_button.setObjectName("dangerButton")  # 危险色描边，降权
        self.restore_button.setToolTip(
            "用所选备份替换当前全部数据，替换前会自动创建保护备份"
        )
        bottom.addWidget(self.restore_button)
        layout.addWidget(tfoot)

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
                self.table.setItem(row, col, item)
        self._apply_row_colors()
        self.count_label.setText(
            f"共 {len(self._infos)} 份备份（自动备份保留最近 30 份，"
            "保护/手动备份不自动清理）"
        )
        self._update_status()

    def _update_status(self) -> None:
        """StatusDot 反映备份健康度：有未通过校验的备份时不点亮。"""
        if not self._infos:
            self.status_dot.set_ok(False)
            self.status_label.setText("尚无备份")
            return
        healthy = all(info.verified for info in self._infos)
        self.status_dot.set_ok(healthy)
        self.status_label.setText(
            "全部备份校验通过"
            if healthy
            else "存在校验未通过的备份，恢复前请先确认"
        )

    def _apply_row_colors(self) -> None:
        """未通过的备份用警示红标出（前景色是显式设置的，QSS 管不到）。"""
        palette = tokens.palette_for(current_mode())
        color = QColor(palette.danger)
        for row, info in enumerate(self._infos):
            if info.verified:
                continue
            for col in range(len(_COLUMNS)):
                item = self.table.item(row, col)
                if item is not None:
                    item.setForeground(color)

    def refresh_theme(self) -> None:
        """主题切换后重算未通过行的文字色（取当前调色板，不依赖 QSS）。"""
        self._apply_row_colors()

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
