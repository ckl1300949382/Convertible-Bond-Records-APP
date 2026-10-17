"""可复用 UI 小组件（UI V2.0 阶段 3）：统计卡。

纯显示层组件：卡片外观由 theme QSS 按 objectName 渲染（statCard / statCardMain），
数值按盈亏着色（盈利红 / 亏损绿 / 零收益中性，中国金融习惯）。
金额变化且卡片可见时做 180ms count-up 动画（QVariantAnimation，无新依赖）；
不可见（如测试、未显示窗口）时直接落定最终值，保证文本随时可断言。
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QVariantAnimation
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from bond_profit.domain.calculations import format_money
from bond_profit.ui import theme
from bond_profit.ui.tokens import SPACE_L, SPACE_M, SPACE_S


class StatCard(QFrame):
    """统计卡：标题 + 大号数值。

    set_money() 金额卡：按符号着色，可见且变化时 count-up；
    set_count() 笔数卡：中性色，不做动画。
    """

    _DURATION_MS = 180  # 克制的数字过渡时长

    def __init__(self, title: str, accent: bool = False, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statCardMain" if accent else "statCard")
        box = QVBoxLayout(self)
        box.setContentsMargins(SPACE_L, SPACE_M, SPACE_L, SPACE_M)
        box.setSpacing(SPACE_S)
        title_label = QLabel(title)
        title_label.setObjectName("statCardTitle")
        self.value_label = QLabel("0.00")
        self.value_label.setObjectName("statCardValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title_label)
        box.addWidget(self.value_label)

        self._current: Decimal | None = None  # 当前显示金额（元）
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(self._DURATION_MS)
        self._anim.valueChanged.connect(self._on_anim_step)

    # ---- 数据入口（主窗口调用） -------------------------------------------------

    def set_money(self, value: Decimal) -> None:
        """金额卡：先按目标值着色；可见且金额变化时 180ms 过渡，否则直接落定。"""
        self._apply_color(value)
        start = self._current
        if start is None or not self.isVisible() or start == value:
            self._show(value)
            return
        self._anim.stop()
        self._anim.setStartValue(float(start))
        self._anim.setEndValue(float(value))
        self._anim.start()

    def set_count(self, value: int) -> None:
        """笔数卡：中性色，不参与动画。"""
        self.value_label.setStyleSheet("")
        self.value_label.setText(f"{value} 笔")

    # ---- 内部 -------------------------------------------------------------------

    def _show(self, value: Decimal) -> None:
        self._current = value
        self.value_label.setText(f"{format_money(value)} 元")

    def _apply_color(self, value: Decimal) -> None:
        """盈利红 / 亏损绿 / 零收益中性（中性态清掉内联色，回落 QSS 默认）。"""
        if value > 0:
            self.value_label.setStyleSheet(f"color: {theme.profit_color().name()};")
        elif value < 0:
            self.value_label.setStyleSheet(f"color: {theme.loss_color().name()};")
        else:
            self.value_label.setStyleSheet("")

    def _on_anim_step(self, current: float) -> None:
        self._current = Decimal(str(current))
        self.value_label.setText(f"{format_money(self._current)} 元")
