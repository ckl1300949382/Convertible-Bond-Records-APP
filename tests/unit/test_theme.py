"""主题模块测试（§3.6）。注册表检测只断言返回合法值。"""

from __future__ import annotations

from PySide6.QtGui import QColor

from bond_profit.ui import theme, tokens


def test_detect_windows_theme_returns_valid_value():
    assert theme.detect_windows_theme() in ("light", "dark")


def test_stylesheet_for_dark_is_qss():
    qss = theme.stylesheet_for("dark")
    assert f"background-color: {tokens.DARK.canvas}" in qss
    assert "QTableWidget" in qss


def test_stylesheet_for_light_is_qss():
    """浅色不再退化为 Qt 默认：与深色同一条渲染路径，只是令牌不同。"""
    light = theme.stylesheet_for("light")
    dark = theme.stylesheet_for("dark")
    assert f"background-color: {tokens.LIGHT.canvas}" in light
    assert "QTableWidget" in light
    assert light != dark
    assert theme.stylesheet_for("unknown") == light  # 未知值按浅色处理


def test_chart_label_color_switches_with_theme():
    dark = theme.chart_label_color("dark")
    light = theme.chart_label_color("light")
    assert isinstance(dark, QColor) and isinstance(light, QColor)
    assert dark != light
    assert dark.lightness() > light.lightness()  # 深色主题下标签更亮


def test_apply_theme_switches_stylesheet(qtbot, qapp):
    theme.apply_theme(qapp, "dark")
    dark = qapp.styleSheet()
    assert "QTableWidget" in dark

    theme.apply_theme(qapp, "light")
    light = qapp.styleSheet()
    assert light != ""  # 浅色也有完整 QSS，不再清空
    assert light != dark
    assert qapp.property(theme.BASE_STYLE_MARK)  # 已切到 Fusion（QSS 才生效）
