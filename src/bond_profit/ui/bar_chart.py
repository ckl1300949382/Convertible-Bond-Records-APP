"""自绘柱状图组件（§3.5，批次 5 重写）。

视觉对应提案 B：圆角渐变柱、行内悬停提示（tooltip）、入场生长动画、
月份标签稀疏显示（12 个月时隔一显示）。涨红跌绿语义不变（§3.2），
柱色实时取自 :mod:`bond_profit.ui.tokens`，主题切换自动跟随。

接口契约（测试依赖，不可变更）：
- ``items`` 属性：原样返回 ``set_data`` 存入的 (标签, 数值) 列表；
- ``set_data``：更新数据并触发重绘；
- ``set_label_color``：显式设置标签色（MainWindow 在主题切换时调用）。

不引入 QtCharts 依赖。
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from bond_profit.domain.calculations import format_money
from bond_profit.ui import tokens
from bond_profit.ui.widgets import current_mode

_MARGIN_H = 6  # 左右留白
_TOP = 22  # 顶部留白（数值标签）
_BOTTOM = 20  # 底部留白（类别标签）
_BAR_RATIO = 0.52  # 柱宽占列宽比例
_CORNER = 3  # 柱顶圆角半径
_TOOLTIP_INTERVAL_MS = 350  # 悬停 tooltip 的刷新节流


class BarChart(QWidget):
    """按 (类别标签, 收益) 列表绘制的柱状图，可含负值。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, Decimal]] = []
        self._label_color = QColor("#555555")
        self._hover_index = -1
        self.setMinimumHeight(170)
        self.setMouseTracking(True)  # 不按下也接收 mouseMove，悬停提示才生效

        # 背景交给 QSS（theme.py 里的 BarChart 规则）。不设的话普通 QWidget
        # 会露出系统调色板的浅灰——QSS 不更新 QPalette，深色下就是一块白。
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # 入场生长动画：set_data 后柱子从零轴长出，420ms 缓出
        self._progress = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(420)
        self._anim.valueChanged.connect(self._on_anim_tick)

    # ------------------------------------------------------------ 数据接口

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
        self._hover_index = -1
        self._anim.stop()
        self._anim.start()  # 数据变了就重播生长动画
        self.update()

    def _on_anim_tick(self, value: object) -> None:
        self._progress = float(value)
        self.update()

    # ------------------------------------------------------------ 事件处理

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        index = self._column_at(event.position())
        if index != self._hover_index:
            self._hover_index = index
            self.update()
            if index >= 0 and index < len(self._items):
                label, value = self._items[index]
                self.setToolTip(f"{label}　{format_money(value)}")
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        self._hover_index = -1
        self.update()
        super().leaveEvent(event)

    def _column_at(self, pos: QPointF) -> int:
        """把鼠标横坐标换算成列号；不在绘图区返回 -1。"""
        if not self._items:
            return -1
        width, height = self.width(), self.height()
        plot_w = width - 2 * _MARGIN_H
        top, bottom = 0, height - _BOTTOM
        if not (_MARGIN_H <= pos.x() <= width - _MARGIN_H):
            return -1
        if not (0 <= pos.y() <= bottom + 6):
            return -1
        col_w = plot_w / len(self._items)
        return int((pos.x() - _MARGIN_H) / col_w)

    # ------------------------------------------------------------ 绘制

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        palette = tokens.palette_for(current_mode())
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
        sparse = len(self._items) > 8  # 12 个月时隔一个显示标签，避免挤成一团

        # 零轴线：发丝级，主题线色
        painter.setPen(QPen(QColor(palette.line_strong), 1))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.drawLine(_MARGIN_H, int(zero_y), width - _MARGIN_H, int(zero_y))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        label_font = painter.font()
        label_font.setPixelSize(10)
        painter.setFont(label_font)

        progress = self._progress

        for index, (label, value) in enumerate(self._items):
            x = _MARGIN_H + index * col_w + (col_w - bar_w) / 2
            hovered = index == self._hover_index
            if value > 0:
                full_h = float(value) * scale
                bar_h = full_h * progress
                painter.setPen(Qt.PenStyle.NoPen)
                painter.fillPath(
                    self._rounded_bar(QRectF(x, zero_y - bar_h, bar_w, bar_h), top=True),
                    self._bar_gradient(palette.profit, QRectF(x, zero_y - full_h, bar_w, full_h), hovered),
                )
                self._draw_value_label(painter, index * col_w + _MARGIN_H, col_w, zero_y - full_h - 14, format_money(value), palette.text_2, hovered)
            elif value < 0:
                full_h = float(-value) * scale
                bar_h = full_h * progress
                painter.setPen(Qt.PenStyle.NoPen)
                painter.fillPath(
                    self._rounded_bar(QRectF(x, zero_y, bar_w, bar_h), top=False),
                    self._bar_gradient(palette.loss, QRectF(x, zero_y, bar_w, full_h), hovered),
                )
                self._draw_value_label(painter, index * col_w + _MARGIN_H, col_w, zero_y + full_h + 4, format_money(value), palette.text_2, hovered)
            else:
                # 零收益：不画柱与数值（一排 0.00 是信息噪音），画一个 2px 中性点占位
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(palette.line_strong))
                painter.drawEllipse(QPointF(_MARGIN_H + index * col_w + col_w / 2, zero_y - 1), 2, 2)

            # 类别标签固定在底部；稀疏模式下奇数位留白
            if not (sparse and index % 2 == 1):
                painter.setPen(QColor(palette.text_3))
                painter.drawText(
                    QRectF(_MARGIN_H + index * col_w, height - _BOTTOM + 4, col_w, 14),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )

    @staticmethod
    def _rounded_bar(rect: QRectF, top: bool) -> QPainterPath:
        """柱形路径：朝向远离零轴的一端圆角，贴零轴的一端直角。"""
        path = QPainterPath()
        r = min(_CORNER, rect.height() / 2)
        if top:
            path.moveTo(rect.left(), rect.bottom())
            path.lineTo(rect.left(), rect.top() + r)
            path.quadTo(rect.left(), rect.top(), rect.left() + r, rect.top())
            path.lineTo(rect.right() - r, rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + r)
            path.lineTo(rect.right(), rect.bottom())
        else:
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.left(), rect.bottom() - r)
            path.quadTo(rect.left(), rect.bottom(), rect.left() + r, rect.bottom())
            path.lineTo(rect.right() - r, rect.bottom())
            path.quadTo(rect.right(), rect.bottom(), rect.right(), rect.bottom() - r)
            path.lineTo(rect.right(), rect.top())
        path.closeSubpath()
        return path

    @staticmethod
    def _bar_gradient(color: str, rect: QRectF, hovered: bool) -> QLinearGradient:
        """竖向渐变：实端在柱头，向零轴方向淡出；悬停时整体加深。"""
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        base = QColor(color)
        base.setAlpha(255 if hovered else 232)
        faded = QColor(color)
        faded.setAlpha(150 if hovered else 110)
        gradient.setColorAt(0, base)
        gradient.setColorAt(1, faded)
        return gradient

    def _draw_value_label(
        self,
        painter: QPainter,
        left: float,
        col_w: float,
        y: float,
        text: str,
        color: str,
        hovered: bool,
    ) -> None:
        """数值标签：默认次要色，悬停列加粗主色。"""
        painter.setPen(QColor(color if not hovered else tokens.palette_for(current_mode()).text))
        painter.drawText(
            QRectF(left, y, col_w, 12),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )
