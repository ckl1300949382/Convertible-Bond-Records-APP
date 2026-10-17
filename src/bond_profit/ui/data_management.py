"""数据管理页（§4）：Excel 模板下载、导入与导出入口。

导入流程：选择文件 → preview_import 解析校验 → ImportPreviewDialog 预览确认
→ commit_import 写入。导入成功后发射 import_completed，由主窗口刷新统计与表格。
导出流程：run_export(query) 写入目标文件；「导出当前筛选结果」按钮只发射
export_filtered_requested 信号，由主窗口在槽内提供当前查询条件——页面不持有
主窗口引用（避免循环引用导致的对象生命周期问题）。
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
from bond_profit.domain.models import RecordQuery
from bond_profit.ui.import_preview_dialog import ImportPreviewDialog


class DataManagementPage(QWidget):
    """数据管理页：模板下载、从 Excel 导入、导出记录。"""

    import_completed = Signal()
    export_filtered_requested = Signal()

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

        export_hint = QLabel("导出内容为六个业务字段加软件计算的收益列。")
        export_hint.setWordWrap(True)
        layout.addWidget(export_hint)

        self.export_all_button = QPushButton("导出全部记录…")
        self.export_all_button.clicked.connect(
            lambda: self.run_export(RecordQuery())
        )
        layout.addWidget(self.export_all_button)

        self.export_filtered_button = QPushButton("导出当前筛选结果…")
        self.export_filtered_button.setToolTip(
            "按总览页当前的搜索/年月筛选条件导出全部匹配记录（不受每页 20 条限制）"
        )
        # 筛选条件由主窗口在槽内提供，页面不回查主窗口状态
        self.export_filtered_button.clicked.connect(
            self.export_filtered_requested.emit
        )
        layout.addWidget(self.export_filtered_button)

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

    # ---- 导出 -----------------------------------------------------------------

    def run_export(self, query: RecordQuery) -> None:
        """按 query 导出记录全集（§4.5），由用户选择保存位置。"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出记录",
            "转债卖出记录.xlsx",
            "Excel 工作簿 (*.xlsx)",
        )
        if not path:
            return
        try:
            count = self._excel.export_records(path, query)
        except ExcelError as exc:  # 无匹配记录 / 写入失败（信息面向用户）
            QMessageBox.information(self, "无法导出", str(exc))
            return
        QMessageBox.information(
            self, "导出完成", f"已导出 {count} 条记录到：\n{path}"
        )
