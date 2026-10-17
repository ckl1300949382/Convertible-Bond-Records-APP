"""自绘柱状图组件（§3.5）。

规则：盈利红色、亏损绿色、零收益中性（不画柱）；数值标签带正负号，
不只依靠颜色；负值柱向零轴下方延伸。不引入 QtCharts 依赖。
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from bond_profit.domain.calculations import format_money

_COLOR_PROFIT = QColor("#c62828")  # 盈利红
_COLOR_LOSS = QColor("#2e7d32")  # 亏损绿
_COLOR_AXIS = QColor("#9e9e9e")  # 零轴线（标签色由 set_label_color 按主题切换）

_MARGIN_H = 8  # 左右留白
_TOP = 26  # 顶部留白（数值标签）
_BOTTOM = 22  # 底部留白（类别标签）
_BAR_RATIO = 0.6  # 柱宽占列宽比例


class BarChart(QWidget):
    """按 (类别标签, 收益) 列表绘制的柱状图，可含负值。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, Decimal]] = []
        self._label_color = QColor("#555555")
        self.setMinimumHeight(170)

    @property
    def items(self) -> list[tuple[str, Decimal]]:
        """当前数据（供测试断言）。"""
        return self._items

    def set_label_color(self, color: QColor) -> None:
        """标签/轴线颜色随主题切换（§3.6）。"""
        self._label_color = QColor(color)
        self.update()

    def set_data(self, items: list[tuple[str, Decimal]]) -> None:
        self._items = list(items)
        self.update()  # 触发重绘

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        width, height = self.width(), self.height()
        plot_w = width - 2 * _MARGIN_H
        plot_h = height - _TOP - _BOTTOM
        if plot_w <= 0 or plot_h <= 0:
            return

        if not self._items:
            painter.setPen(self._label_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return

        max_pos = max((Decimal("0"), *(v for _, v in self._items)))
        max_neg = max((Decimal("0"), *(-v for _, v in self._items)))
        # 全为零时零轴放中间，避免除零
        span = max_pos + max_neg if (max_pos + max_neg) > 0 else Decimal("1")
        zero_y = _TOP + float(max_pos / span) * plot_h
        scale = plot_h / float(span)

        col_w = plot_w / len(self._items)
        bar_w = col_w * _BAR_RATIO

        label_font = QFont()
        label_font.setPointSize(7)
        painter.setFont(label_font)

        # 零轴线
        painter.setPen(QPen(_COLOR_AXIS, 1))
        painter.drawLine(_MARGIN_H, int(zero_y), width - _MARGIN_H, int(zero_y))

        for index, (label, value) in enumerate(self._items):
            x = _MARGIN_H + index * col_w + (col_w - bar_w) / 2
            text = format_money(value)
            if value > 0:
                bar_h = float(value) * scale
                painter.fillRect(QRectF(x, zero_y - bar_h, bar_w, bar_h), _COLOR_PROFIT)
                painter.setPen(self._label_color)
                painter.drawText(
                    QRectF(_MARGIN_H + index * col_w, zero_y - bar_h - _TOP + 6, col_w, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )
            elif value < 0:
                bar_h = float(-value) * scale
                painter.fillRect(QRectF(x, zero_y, bar_w, bar_h), _COLOR_LOSS)
                painter.setPen(self._label_color)
                painter.drawText(
                    QRectF(_MARGIN_H + index * col_w, zero_y + bar_h + 2, col_w, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )
            else:  # 零收益：不画柱，数值仍显示（§3.5 中性 + 带符号数字）
                painter.setPen(self._label_color)
                painter.drawText(
                    QRectF(_MARGIN_H + index * col_w, _TOP - 14, col_w, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )

            # 类别标签固定在底部
            painter.drawText(
                QRectF(_MARGIN_H + index * col_w, height - _BOTTOM + 4, col_w, 14),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
