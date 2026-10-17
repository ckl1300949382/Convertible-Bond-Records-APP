"""新增/编辑记录弹窗（文档 §3.4）。

紧凑双列布局；校验失败在对应输入框下方显示中文错误提示，不覆盖用户输入；
保存成功关闭弹窗并刷新列表；保存失败弹窗保持、输入保留；
未保存修改时按 Esc 或关闭 → 确认放弃。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bond_profit.application.sales_service import SalesService
from bond_profit.domain.models import SaleRecord

_ERROR_STYLE = "color: #c62828;"

# 错误信息关键字 → 字段（领域层错误信息措辞可控，映射稳定）
_FIELD_KEYWORDS = (
    ("名称", "name"),
    ("代码", "code"),
    ("日期", "date"),
    ("价格", "price"),
    ("数量", "quantity"),
    ("备注", "note"),
)


class RecordDialog(QDialog):
    def __init__(
        self,
        service: SalesService,
        record: SaleRecord | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._record = record
        self._dirty = False

        self.setWindowTitle("编辑记录" if record else "新增记录")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_record()
        self._track_dirty()

    # ---- 界面构建 ----------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)

        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.code_edit.setMaxLength(6)
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.price_edit = QLineEdit()
        self.price_edit.setPlaceholderText("如 130.00")
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999_999_999)
        self.quantity_spin.setValue(10)  # §2.1 默认 10 张
        self.note_edit = QLineEdit()
        self.note_edit.setMaxLength(500)

        self.name_error = QLabel()
        self.code_error = QLabel()
        self.date_error = QLabel()
        self.price_error = QLabel()
        self.quantity_error = QLabel()
        self.note_error = QLabel()
        self.general_error = QLabel()
        self.general_error.setStyleSheet(_ERROR_STYLE)
        self.general_error.setWordWrap(True)
        self.general_error.hide()

        self._error_labels = {
            "name": self.name_error,
            "code": self.code_error,
            "date": self.date_error,
            "price": self.price_error,
            "quantity": self.quantity_error,
            "note": self.note_error,
        }
        for label in self._error_labels.values():
            label.setStyleSheet(_ERROR_STYLE)
            label.setWordWrap(True)
            label.hide()

        grid.addWidget(self._field_group("转债名称", self.name_edit, self.name_error), 0, 0)
        grid.addWidget(self._field_group("卖出日期", self.date_edit, self.date_error), 0, 1)
        grid.addWidget(self._field_group("转债代码", self.code_edit, self.code_error), 1, 0)
        grid.addWidget(self._field_group("卖出价格(元)", self.price_edit, self.price_error), 1, 1)
        grid.addWidget(self._field_group("卖出数量(张)", self.quantity_spin, self.quantity_error), 2, 0)
        grid.addWidget(self._field_group("备注(可选)", self.note_edit, self.note_error), 2, 1)
        layout.addLayout(grid)

        layout.addWidget(self.general_error)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = QPushButton("取消")
        self.save_button = QPushButton("保存")
        self.save_button.setDefault(True)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

        self.save_button.clicked.connect(self._on_save)
        self.cancel_button.clicked.connect(self.reject)

    @staticmethod
    def _field_group(title: str, editor: QWidget, error_label: QLabel) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(QLabel(title))
        layout.addWidget(editor)
        layout.addWidget(error_label)
        return box

    def _load_record(self) -> None:
        if self._record is None:
            self.date_edit.setDate(QDate.currentDate())
            return
        record = self._record
        self.name_edit.setText(record.bond_name)
        self.code_edit.setText(record.bond_code)
        self.date_edit.setDate(
            QDate(record.sale_date.year, record.sale_date.month, record.sale_date.day)
        )
        self.price_edit.setText(f"{record.sale_price:.2f}")
        self.quantity_spin.setValue(record.quantity)
        self.note_edit.setText(record.note)

    def _track_dirty(self) -> None:
        self.name_edit.textChanged.connect(self._mark_dirty)
        self.code_edit.textChanged.connect(self._mark_dirty)
        self.date_edit.dateChanged.connect(self._mark_dirty)
        self.price_edit.textChanged.connect(self._mark_dirty)
        self.quantity_spin.valueChanged.connect(self._mark_dirty)
        self.note_edit.textChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    # ---- 保存 --------------------------------------------------------------

    def _on_save(self) -> None:
        self._clear_errors()

        price = self._parse_price()
        if price is None:
            self._show_field_error("price", "卖出价格必须是数字，最多两位小数")
            return

        record = SaleRecord(
            bond_name=self.name_edit.text(),
            bond_code=self.code_edit.text(),
            sale_date=self._qdate_to_date(self.date_edit.date()),
            sale_price=price,
            quantity=self.quantity_spin.value(),
            note=self.note_edit.text(),
            id=self._record.id if self._record else None,
            created_at=self._record.created_at if self._record else None,
        )

        if self._record is None:
            result = self._service.create_record(record)
        else:
            result = self._service.update_record(record)

        if result.ok:
            self._dirty = False
            self.accept()
            return

        errors = list(result.errors)
        if result.failure:
            errors.append(result.failure)
        self._display_errors(errors)

    def _parse_price(self) -> Decimal | None:
        text = self.price_edit.text().strip()
        if not text:
            return Decimal(0)  # 交给领域校验提示「必须大于0」
        try:
            return Decimal(text)
        except InvalidOperation:
            return None

    @staticmethod
    def _qdate_to_date(qdate: QDate) -> date:
        return date(qdate.year(), qdate.month(), qdate.day())

    # ---- 错误显示 ----------------------------------------------------------

    def _display_errors(self, errors: list[str]) -> None:
        mapped: set[str] = set()
        for error in errors:
            for keyword, key in _FIELD_KEYWORDS:
                if keyword in error and key not in mapped:
                    self._show_field_error(key, error)
                    mapped.add(key)
                    break
            else:
                self.general_error.setText(error)
                self.general_error.show()

    def _show_field_error(self, key: str, message: str) -> None:
        label = self._error_labels[key]
        label.setText(message)
        label.show()

    def _clear_errors(self) -> None:
        for label in self._error_labels.values():
            label.hide()
            label.clear()
        self.general_error.hide()
        self.general_error.clear()

    # ---- 关闭保护（§3.4 未保存修改确认） ------------------------------------

    def reject(self) -> None:  # Esc 与「取消」按钮
        if self._dirty and not self._confirm_discard():
            return
        super().reject()

    def closeEvent(self, event) -> None:  # 标题栏关闭按钮
        if self._dirty and not self._confirm_discard():
            event.ignore()
            return
        event.accept()

    @staticmethod
    def _confirm_discard() -> bool:
        answer = QMessageBox.question(
            None,
            "放弃修改",
            "当前修改尚未保存，确定要放弃吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
