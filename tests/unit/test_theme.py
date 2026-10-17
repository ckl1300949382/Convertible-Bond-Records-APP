"""主题模块测试（§3.6 + UI V2.0 阶段 1）。注册表检测只断言返回合法值。"""

from __future__ import annotations

from PySide6.QtGui import QColor

from bond_profit.ui import theme, tokens


def test_detect_windows_theme_returns_valid_value():
    assert theme.detect_windows_theme() in ("light", "dark")


def test_stylesheet_for_dark_uses_dark_palette():
    qss = theme.stylesheet_for("dark")
    assert "QTableWidget" in qss
    assert f"background-color: {tokens.DARK.window}" in qss  # 深海蓝黑


def test_stylesheet_for_light_is_full_custom_qss():
    """V2.0：浅色不再是 Qt 默认（空 QSS），而是珍珠白定制主题。"""
    qss = theme.stylesheet_for("light")
    assert "QTableWidget" in qss
    assert f"background-color: {tokens.LIGHT.window}" in qss


def test_stylesheet_for_unknown_mode_falls_back_to_light():
    assert theme.stylesheet_for("unknown") == theme.stylesheet_for("light")


def test_chart_label_color_switches_with_theme():
    dark = theme.chart_label_color("dark")
    light = theme.chart_label_color("light")
    assert isinstance(dark, QColor) and isinstance(light, QColor)
    assert dark != light
    assert dark.lightness() > light.lightness()  # 深色主题下标签更亮


def test_chart_colors_follow_chinese_profit_loss_convention():
    """盈亏遵循中国金融习惯：盈利红、亏损绿；深色模式亮度更高保证对比度。"""
    dark = theme.chart_colors("dark")
    light = theme.chart_colors("light")
    for colors in (dark, light):
        assert colors["profit"].red() > colors["profit"].green()
        assert colors["loss"].green() > colors["loss"].red()
    assert dark["profit"].lightness() > light["profit"].lightness()
    assert dark["loss"].lightness() > light["loss"].lightness()


def test_semantic_colors_follow_mode():
    """语义色取自对应主题令牌。"""
    assert theme.profit_color("dark").name() == QColor(tokens.DARK.profit).name()
    assert theme.loss_color("light").name() == QColor(tokens.LIGHT.loss).name()
    assert theme.error_color("dark").name() == QColor(tokens.DARK.danger).name()
    assert theme.warning_color("light").name() == QColor(tokens.LIGHT.warning).name()


def test_apply_theme_sets_stylesheet_for_both_modes(qtbot, qapp):
    try:
        theme.apply_theme(qapp, "dark")
        assert f"background-color: {tokens.DARK.window}" in qapp.styleSheet()

        theme.apply_theme(qapp, "light")
        assert f"background-color: {tokens.LIGHT.window}" in qapp.styleSheet()
    finally:
        qapp.setStyleSheet("")  # 全局样式不泄漏到其他测试


def test_active_mode_tracks_apply_theme(qtbot, qapp):
    try:
        theme.apply_theme(qapp, "dark")
        assert theme.active_mode() == "dark"
        assert theme.error_qss() == f"color: {tokens.DARK.danger};"

        theme.apply_theme(qapp, "light")
        assert theme.active_mode() == "light"
        assert theme.error_qss() == f"color: {tokens.LIGHT.danger};"
    finally:
        qapp.setStyleSheet("")


def test_apply_calendar_formats_follows_theme(qtbot, qapp):
    """日历星期表头配色随主题（深色对比度修复）：工作日弱化、周末红。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCalendarWidget

    calendar = QCalendarWidget()
    qtbot.addWidget(calendar)

    theme.apply_calendar_formats(calendar, "dark")
    monday = calendar.weekdayTextFormat(Qt.DayOfWeek.Monday)
    saturday = calendar.weekdayTextFormat(Qt.DayOfWeek.Saturday)
    assert monday.foreground().color().name() == QColor(tokens.DARK.text_muted).name()
    assert saturday.foreground().color().name() == QColor(tokens.DARK.profit).name()

    theme.apply_calendar_formats(calendar, "light")
    monday = calendar.weekdayTextFormat(Qt.DayOfWeek.Monday)
    saturday = calendar.weekdayTextFormat(Qt.DayOfWeek.Saturday)
    assert monday.foreground().color().name() == QColor(tokens.LIGHT.text_muted).name()
    assert saturday.foreground().color().name() == QColor(tokens.LIGHT.profit).name()
