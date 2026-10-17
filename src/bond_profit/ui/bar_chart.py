"""自绘柱状图组件（§3.5 + UI V2.0 阶段 5）。

规则：盈利红色、亏损绿色、零收益中性（不画柱）；数值标签带正负号，
不只依靠颜色；负值柱向零轴下方延伸。不引入 QtCharts 依赖。

阶段 5 视觉升级：圆角柱 + 纵向渐变、淡网格虚线、悬浮高亮与数值提示、
约 200ms 入场生长动画（QVariantAnimation，无新依赖）；
数据未变化时 set_data 不重播动画，避免搜索逐键刷新时闪烁。
对外接口（items / set_data / set_label_color / apply_mode）不变。
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from bond_profit.domain.calculations import format_money
from bond_profit.ui import theme

_MARGIN_H = 8  # 左右留白
_TOP = 26  # 顶部留白（数值标签）
_BOTTOM = 22  # 底部留白（类别标签）
_BAR_RATIO = 0.6  # 柱宽占列宽比例
_BAR_RADIUS = 3.0  # 圆角柱半径（px），克制
_ANIM_MS = 200  # 入场生长动画时长

_LIGHT_COLORS = theme.chart_colors("light")  # 默认浅色（测试可独立实例化）


class BarChart(QWidget):
    """按 (类别标签, 收益) 列表绘制的柱状图，可含负值。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, Decimal]] = []
        self._label_color = QColor(theme.CHART_LABEL_LIGHT)
        self._color_profit = QColor(_LIGHT_COLORS["profit"])
        self._color_loss = QColor(_LIGHT_COLORS["loss"])
        self._color_axis = QColor(_LIGHT_COLORS["axis"])
        self._color_grid = QColor(_LIGHT_COLORS["grid"])
        self._hover_index: int | None = None
        self._progress = 1.0  # 入场动画进度（1.0 = 完整柱高）
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)
        self.setMouseTracking(True)  # 悬浮高亮与数值提示
        self.setMinimumHeight(170)

    @property
    def items(self) -> list[tuple[str, Decimal]]:
        """当前数据（供测试断言）。"""
        return self._items

    def set_label_color(self, color: QColor) -> None:
        """仅设置标签色（保留旧接口；主题切换请用 apply_mode）。"""
        self._label_color = QColor(color)
        self.update()

    def apply_mode(self, mode: str) -> None:
        """标签/轴线/网格/盈亏柱颜色随主题切换（UI V2.0：盈红亏绿随主题调亮度）。"""
        colors = theme.chart_colors(mode)
        self._label_color = QColor(theme.chart_label_color(mode))
        self._color_profit = QColor(colors["profit"])
        self._color_loss = QColor(colors["loss"])
        self._color_axis = QColor(colors["axis"])
        self._color_grid = QColor(colors["grid"])
        self.update()

    def set_data(self, items: list[tuple[str, Decimal]]) -> None:
        new_items = list(items)
        changed = new_items != self._items
        self._items = new_items
        self._hover_index = None
        if changed and self.isVisible():
            # 数据变化且可见：重播入场生长动画；不可见（含测试）直接落定
            self._anim.stop()
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.start()
        else:
            self._progress = 1.0
        self.update()  # 触发重绘

    # ---- 动画 / 悬浮 -----------------------------------------------------------

    def _on_anim_step(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    def _column_at(self, x: float) -> int | None:
        """返回横坐标所在列号；无数据或越界返回 None。"""
        plot_w = self.width() - 2 * _MARGIN_H
        if not self._items or plot_w <= 0:
            return None
        index = int((x - _MARGIN_H) // (plot_w / len(self._items)))
        return index if 0 <= index < len(self._items) else None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        index = self._column_at(event.position().x())
        if index != self._hover_index:
            self._hover_index = index
            self.update()
        if index is not None:
            label, value = self._items[index]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{label}：{format_money(value)} 元",
                self,
            )
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        if self._hover_index is not None:
            self._hover_index = None
            self.update()
        super().leaveEvent(event)

    # ---- 绘制 ------------------------------------------------------------------

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

        # 淡网格：零轴上下各一条半程虚线（阶段 5），弱于零轴线
        grid_pen = QPen(self._color_grid, 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        if max_pos > 0:
            y = int(zero_y - float(max_pos) * scale / 2)
            painter.drawLine(_MARGIN_H, y, width - _MARGIN_H, y)
        if max_neg > 0:
            y = int(zero_y + float(max_neg) * scale / 2)
            painter.drawLine(_MARGIN_H, y, width - _MARGIN_H, y)

        # 零轴线
        painter.setPen(QPen(self._color_axis, 1))
        painter.drawLine(_MARGIN_H, int(zero_y), width - _MARGIN_H, int(zero_y))

        for index, (label, value) in enumerate(self._items):
            x = _MARGIN_H + index * col_w + (col_w - bar_w) / 2
            text = format_money(value)
            hovered = index == self._hover_index
            if value > 0:
                bar_h = float(value) * scale * self._progress
                base = self._color_profit.lighter(112) if hovered else self._color_profit
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.fillPath(
                    self._bar_path(x, zero_y - bar_h, bar_w, bar_h, rounded_top=True),
                    self._bar_brush(base, y_free=zero_y - bar_h, y_axis=zero_y),
                )
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                painter.setPen(self._label_color)
                painter.drawText(
                    QRectF(_MARGIN_H + index * col_w, zero_y - bar_h - _TOP + 6, col_w, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )
            elif value < 0:
                bar_h = float(-value) * scale * self._progress
                base = self._color_loss.lighter(112) if hovered else self._color_loss
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.fillPath(
                    self._bar_path(x, zero_y, bar_w, bar_h, rounded_top=False),
                    self._bar_brush(base, y_free=zero_y + bar_h, y_axis=zero_y),
                )
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
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

    # ---- 绘制辅助 ---------------------------------------------------------------

    @staticmethod
    def _bar_path(
        x: float, y: float, w: float, h: float, rounded_top: bool
    ) -> QPainterPath:
        """柱体路径：正值柱圆顶部两角、负值柱圆底部两角（圆角只留在自由端）。"""
        path = QPainterPath()
        if w <= 0 or h <= 0:
            return path
        r = min(_BAR_RADIUS, w / 2, h)
        if rounded_top:
            path.moveTo(x, y + h)
            path.lineTo(x, y + r)
            path.quadTo(x, y, x + r, y)
            path.lineTo(x + w - r, y)
            path.quadTo(x + w, y, x + w, y + r)
            path.lineTo(x + w, y + h)
        else:
            path.moveTo(x, y)
            path.lineTo(x + w, y)
            path.lineTo(x + w, y + h - r)
            path.quadTo(x + w, y + h, x + w - r, y + h)
            path.lineTo(x + r, y + h)
            path.quadTo(x, y + h, x, y + h - r)
        path.closeSubpath()
        return path

    @staticmethod
    def _bar_brush(color: QColor, y_free: float, y_axis: float) -> QLinearGradient:
        """纵向渐变：自由端（生长端）微亮，靠零轴处为基色；悬浮时整体提亮。"""
        gradient = QLinearGradient(0, y_free, 0, y_axis)
        gradient.setColorAt(0.0, color.lighter(118))
        gradient.setColorAt(1.0, color)
        return gradient
