"""主窗口：左侧导航（总览 / 数据管理 / 备份与恢复）+ 页面栈。

总览页：记录表格与增删改（阶段 1）、统计卡片、搜索/筛选/排序/分页（§3.2/§3.3）、
图表（批次 7）。数据管理页（批次 10）：Excel 模板下载与导入（§4）。
备份与恢复页（批次 16）：手动备份、备份列表、恢复、自动备份检查（§6）。
"""

from __future__ import annotations

from decimal import Decimal

import bond_profit
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bond_profit.application.backup_service import BackupService, RestoreError
from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.domain.calculations import format_money, profit_per_record
from bond_profit.domain.money import cents_to_yuan
from bond_profit.domain.models import RecordQuery, SaleRecord
from bond_profit.infrastructure.backup import BackupError
from bond_profit.infrastructure.logging import current_log_dir
from bond_profit.ui import prefs, theme
from bond_profit.ui.backup_page import BackupPage
from bond_profit.ui.bar_chart import BarChart
from bond_profit.ui.data_management import DataManagementPage
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
    _AUTO_BACKUP_INTERVAL_MS = 30 * 60 * 1000  # §6.1：运行期间每 30 分钟检查一次

    def __init__(
        self,
        service: SalesService,
        excel_service: ExcelService,
        settings_path: str | None = None,
        backup_service: BackupService | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._backup = backup_service
        self._settings = prefs.open_settings(settings_path)
        self._records: list[SaleRecord] = []
        self._page = 1
        self._total = 0

        # 窗口尺寸与表格排序不持久化（2026-10-29：改 UI 时避免旧偏好与新布局冲突）
        self._sort_key = "date"
        self._sort_desc = True

        self.setWindowTitle(f"可转债收益记录 v{bond_profit.__version__}")
        self.resize(1080, 760)

        central = QWidget()
        central.setObjectName("root")  # 供 QSS 定位背景，避免用裸 QWidget{} 选择器
        root = QHBoxLayout(central)

        # ---- 左侧导航（§3.1 总览 / 数据管理） --------------------------------
        self.nav_list = QListWidget()
        self.nav_list.addItems(["总览", "数据管理", "备份与恢复"])
        self.nav_list.setFixedWidth(140)
        root.addWidget(self.nav_list)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, stretch=1)

        overview_page = QWidget()
        layout = QVBoxLayout(overview_page)

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

        self.theme_button = QPushButton("主题")  # 文本在 _apply_theme_mode 设置
        self.theme_button.setFixedWidth(64)
        self.theme_button.setToolTip("在浅色/深色之间切换，选择会被记住")
        toolbar.addWidget(self.theme_button)

        # 日志入口（阶段 5）：打开日志文件夹，便于用户整包拷贝反馈问题
        self.log_button = QPushButton("打开日志")
        self.log_button.setToolTip("打开日志文件夹；反馈问题时可将整个文件夹发给我们")
        self.log_button.clicked.connect(self._on_open_logs)
        toolbar.addWidget(self.log_button)

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

        # ---- 图表区（§3.5）：月度（可选年份）与年度柱状图 ----------------------
        charts_row = QHBoxLayout()

        monthly_frame = QFrame()
        monthly_box = QVBoxLayout(monthly_frame)
        monthly_header = QHBoxLayout()
        monthly_header.addWidget(QLabel("月度收益"))
        monthly_header.addStretch()
        self.chart_year_combo = QComboBox()
        self.chart_year_combo.setEnabled(False)  # 无记录时不可选
        monthly_header.addWidget(self.chart_year_combo)
        monthly_box.addLayout(monthly_header)
        self.monthly_chart = BarChart()
        monthly_box.addWidget(self.monthly_chart)
        charts_row.addWidget(monthly_frame, stretch=1)

        yearly_frame = QFrame()
        yearly_box = QVBoxLayout(yearly_frame)
        yearly_box.addWidget(QLabel("年度收益"))
        self.yearly_chart = BarChart()
        yearly_box.addWidget(self.yearly_chart)
        charts_row.addWidget(yearly_frame, stretch=1)

        table_layout.addLayout(charts_row)

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
        _section_for_key = {key: sec for sec, key in _SORTABLE_COLUMNS.items()}
        header.setSortIndicator(
            _section_for_key[self._sort_key],
            Qt.SortOrder.DescendingOrder
            if self._sort_desc
            else Qt.SortOrder.AscendingOrder,
        )
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

        # 总览页完成，加入页面栈；数据管理页由批次 10 提供（§4）
        self.pages.addWidget(overview_page)
        self.data_page = DataManagementPage(excel_service)
        self.data_page.export_filtered_requested.connect(self._on_export_filtered)
        self.pages.addWidget(self.data_page)
        # 备份与恢复页（批次 16 / §6）：信号式接线，页面不持有服务对象
        self.backup_page = BackupPage()
        self.backup_page.manual_backup_requested.connect(self._on_manual_backup)
        self.backup_page.restore_requested.connect(self._on_restore_backup)
        self.backup_page.check_requested.connect(self._on_auto_backup_check)
        self.backup_page.refresh_requested.connect(self._refresh_backup_list)
        self.pages.addWidget(self.backup_page)

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
        self.chart_year_combo.currentIndexChanged.connect(self._on_chart_year_changed)
        self.theme_button.clicked.connect(self._on_toggle_theme)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.data_page.import_completed.connect(self.refresh_records)
        self.nav_list.setCurrentRow(0)  # 默认进入总览页

        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._on_focus_search)
        new_record_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_record_shortcut.activated.connect(self._on_add)

        # 自动备份定期检查（§6.1）；未配置备份服务时（部分测试场景）不启动
        self._backup_timer = QTimer(self)
        self._backup_timer.setInterval(self._AUTO_BACKUP_INTERVAL_MS)
        self._backup_timer.timeout.connect(self._on_auto_backup_check)
        if backup_service is not None:
            self._backup_timer.start()

        # 应用已保存的主题（§3.6：首次跟随 Windows，手动切换后记住选择）
        self._apply_theme_mode(prefs.resolve_theme(self._settings), save=False)

        self.refresh_records()
        self._refresh_backup_list()  # 初始填充备份列表（未配置备份服务时为空操作）

    # ---- 导航 -----------------------------------------------------------------

    def _on_nav_changed(self, index: int) -> None:
        """左侧导航切换页面（总览 / 数据管理 / 备份与恢复）。"""
        self.pages.setCurrentIndex(index)

    def _on_export_filtered(self) -> None:
        """按总览页当前搜索/筛选条件导出全集（§4.5 XLS-09）。"""
        self.data_page.run_export(self._build_query())

    # ---- 备份与恢复（§6） -------------------------------------------------------

    def _refresh_backup_list(self) -> None:
        if self._backup is None:
            return
        self.backup_page.populate_backups(self._backup.list_backups())

    def _on_manual_backup(self, dest_dir: str) -> None:
        if self._backup is None:
            return
        try:
            info = self._backup.run_manual_backup(dest_dir)
        except BackupError as exc:
            QMessageBox.warning(self, "备份失败", str(exc))
            return
        self._refresh_backup_list()
        QMessageBox.information(
            self,
            "备份成功",
            f"手动备份已创建：{info.path}\n包含 {info.record_count} 条记录。",
        )

    def _on_auto_backup_check(self) -> None:
        if self._backup is None:
            return
        try:
            info = self._backup.run_auto_backup()
        except BackupError as exc:
            # BAK-03：醒目但不阻断录入；备份页「立即检查」可重试
            self.statusBar().showMessage(f"自动备份失败：{exc}", 10000)
            return
        self._refresh_backup_list()
        if info is not None:
            self.statusBar().showMessage(
                f"自动备份完成：{info.created_at}（{info.record_count} 条记录）",
                10000,
            )

    def _on_restore_backup(self, path: str) -> None:
        if self._backup is None:
            return
        try:
            report = self._backup.restore_from_backup(path)
        except (BackupError, RestoreError) as exc:
            QMessageBox.warning(self, "恢复失败", str(exc))
            return
        self.refresh_records()  # §66：恢复后表格、卡片、图表同步刷新
        self._refresh_backup_list()
        QMessageBox.information(
            self,
            "恢复成功",
            f"已从备份恢复 {report.record_count} 条记录，"
            f"累计收益 {format_money(cents_to_yuan(report.total_profit_cents))} 元。\n"
            f"恢复前的保护备份：{report.protected.path.name}",
        )

    # ---- 主题（§3.6） ---------------------------------------------------------

    def _on_open_logs(self) -> None:
        """打开日志文件夹（阶段 5 日志复制入口）。"""
        log_dir = current_log_dir()
        if log_dir is None or not log_dir.is_dir():
            QMessageBox.information(self, "打开日志", "尚未生成日志文件夹。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))

    def _apply_theme_mode(self, mode: str, save: bool = True) -> None:
        """应用浅/深色主题；save=True 时把选择写入偏好。"""
        application = QApplication.instance()
        if application is not None:
            theme.apply_theme(application, mode)
        label_color = theme.chart_label_color(mode)
        self.monthly_chart.set_label_color(label_color)
        self.yearly_chart.set_label_color(label_color)
        self.theme_button.setText("深色" if mode == "dark" else "浅色")
        self.theme_button.setToolTip("当前为{}主题，点击切换".format(
            "深色" if mode == "dark" else "浅色"
        ))
        if save:
            prefs.save_theme(self._settings, mode)

    def _on_toggle_theme(self) -> None:
        current = "dark" if self.theme_button.text() == "深色" else "light"
        self._apply_theme_mode("light" if current == "dark" else "dark")

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
        self._refresh_charts()
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

    def _refresh_charts(self) -> None:
        """刷新月度/年度柱状图（§3.5），增删改后经 refresh_records 同步刷新。"""
        years = self._service.distinct_years()
        current = self.chart_year_combo.currentData()
        self.chart_year_combo.blockSignals(True)
        self.chart_year_combo.clear()
        for year in years:
            self.chart_year_combo.addItem(f"{year} 年", year)
        if current in years:
            self.chart_year_combo.setCurrentIndex(self.chart_year_combo.findData(current))
        elif years:
            self.chart_year_combo.setCurrentIndex(0)  # 默认最新年份
        self.chart_year_combo.setEnabled(bool(years))
        self.chart_year_combo.blockSignals(False)

        year = self.chart_year_combo.currentData()
        monthly = self._service.monthly_profits(year) if year is not None else [Decimal("0")] * 12
        self.monthly_chart.set_data(
            [(f"{month} 月", value) for month, value in enumerate(monthly, 1)]
        )
        self.yearly_chart.set_data(
            [(str(year), value) for year, value in self._service.yearly_profits()]
        )

    def _on_chart_year_changed(self) -> None:
        self._refresh_charts()

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
