"""StatCard 统计卡测试（UI V2.0 阶段 3）：文本格式、盈亏着色、隐藏时不做动画。

卡片未被 show() 时 set_money 必须立即落定最终文本（count-up 仅在可见时触发），
这也是全部既有统计卡测试不感知动画的前提。
"""

from __future__ import annotations

from decimal import Decimal

from bond_profit.ui import theme, tokens
from bond_profit.ui.widgets import StatCard


def test_set_money_formats_with_sign_and_unit(qtbot):
    card = StatCard("累计收益")
    qtbot.addWidget(card)

    card.set_money(Decimal("400.00"))
    assert card.value_label.text() == "+400.00 元"

    card.set_money(Decimal("-15.50"))
    assert card.value_label.text() == "-15.50 元"


def test_set_money_zero_is_neutral(qtbot):
    card = StatCard("累计收益")
    qtbot.addWidget(card)

    card.set_money(Decimal("0"))
    assert card.value_label.text() == "0.00 元"
    assert "color" not in card.value_label.styleSheet()  # 零收益中性


def test_money_color_follows_chinese_convention_per_mode(qtbot, qapp):
    """盈利红 / 亏损绿，色值取自当前主题令牌（浅/深各验证一次）。"""
    card = StatCard("累计收益")
    qtbot.addWidget(card)

    try:
        theme.apply_theme(qapp, "light")
        card.set_money(Decimal("10.00"))
        assert card.value_label.styleSheet() == f"color: {tokens.LIGHT.profit};"
        card.set_money(Decimal("-5.00"))
        assert card.value_label.styleSheet() == f"color: {tokens.LIGHT.loss};"

        theme.apply_theme(qapp, "dark")
        card.set_money(Decimal("10.00"))
        assert card.value_label.styleSheet() == f"color: {tokens.DARK.profit};"
    finally:
        qapp.setStyleSheet("")  # 全局样式不泄漏到其他测试


def test_set_count_neutral_with_unit(qtbot):
    card = StatCard("累计卖出笔数")
    qtbot.addWidget(card)

    card.set_count(7)
    assert card.value_label.text() == "7 笔"
    assert "color" not in card.value_label.styleSheet()


def test_hidden_card_lands_final_text_immediately(qtbot):
    """未显示的卡片不做动画：set_money 后文本即为最终值（既有 UI 测试依赖此行为）。"""
    card = StatCard("累计收益")
    qtbot.addWidget(card)
    assert not card.isVisible()

    card.set_money(Decimal("1854.00"))
    assert card.value_label.text() == "+1854.00 元"
