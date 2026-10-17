"""主题模块测试（§3.6）。注册表检测只断言返回合法值。"""

from __future__ import annotations

from PySide6.QtGui import QColor

from bond_profit.ui import theme


def test_detect_windows_theme_returns_valid_value():
    assert theme.detect_windows_theme() in ("light", "dark")


def test_stylesheet_for_dark_is_qss():
    qss = theme.stylesheet_for("dark")
    assert "background-color: #2b2b2b" in qss
    assert "QTableWidget" in qss


def test_stylesheet_for_light_is_empty():
    assert theme.stylesheet_for("light") == ""
    assert theme.stylesheet_for("unknown") == ""  # 未知值按浅色处理


def test_chart_label_color_switches_with_theme():
    dark = theme.chart_label_color("dark")
    light = theme.chart_label_color("light")
    assert isinstance(dark, QColor) and isinstance(light, QColor)
    assert dark != light
    assert dark.lightness() > light.lightness()  # 深色主题下标签更亮


def test_apply_theme_sets_and_clears_stylesheet(qtbot, qapp):
    theme.apply_theme(qapp, "dark")
    assert "QTableWidget" in qapp.styleSheet()

    theme.apply_theme(qapp, "light")
    assert qapp.styleSheet() == ""
