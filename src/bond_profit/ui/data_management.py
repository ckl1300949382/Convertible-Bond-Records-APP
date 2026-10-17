"""数据管理页（§4）：Excel 模板下载与导入入口。

导入流程：选择文件 → preview_import 解析校验 → ImportPreviewDialog 预览确认
→ commit_import 写入。导入成功后发射 import_completed，由主窗口刷新统计与表格。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bond_profit.application.excel_service import ExcelError, ExcelService
from bond_profit.ui.import_preview_dialog import ImportPreviewDialog


class DataManagementPage(QWidget):
    """数据管理页：模板下载、从 Excel 导入。"""

    import_completed = Signal()

    def __init__(self, excel_service: ExcelService, parent=None) -> None:
        super().__init__(parent)
        self._excel = excel_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("数据管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "通过 Excel 批量录入卖出记录：先下载模板并按「填写说明」页填写，"
            "再选择文件导入。导入前会逐行校验并预览，确认后一次性写入；"
            "与已有记录完全相同的行会自动跳过。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.template_button = QPushButton("下载 Excel 模板")
        self.template_button.clicked.connect(self._on_download_template)
        layout.addWidget(self.template_button)

        self.import_button = QPushButton("从 Excel 导入…")
        self.import_button.clicked.connect(self._on_import)
        layout.addWidget(self.import_button)

        layout.addStretch()

    # ---- 动作 -----------------------------------------------------------------

    def _on_download_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 Excel 模板",
            "转债卖出记录模板.xlsx",
            "Excel 工作簿 (*.xlsx)",
        )
        if not path:
            return
        try:
            self._excel.generate_template(path)
        except OSError as exc:
            QMessageBox.warning(self, "模板保存失败", f"无法写入文件：{exc}")
            return
        QMessageBox.information(self, "模板已保存", f"模板已保存到：\n{path}")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择要导入的 Excel 文件", "", "Excel 工作簿 (*.xlsx)"
        )
        if not path:
            return
        try:
            preview = self._excel.preview_import(path)
        except ExcelError as exc:  # 文件级错误：打不开、缺列等
            QMessageBox.warning(self, "无法导入", str(exc))
            return
        dialog = ImportPreviewDialog(self._excel, preview, parent=self)
        if dialog.exec():
            self.import_completed.emit()
