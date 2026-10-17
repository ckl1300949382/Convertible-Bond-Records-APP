"""主题管理（§3.6）：跟随 Windows 浅/深色，手动切换后保存偏好。

深色用一份精简 QSS 调色板；浅色即 Qt 默认样式，清空 QSS。
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

# 图表标签色随主题切换（BarChart 自绘，不适用 QSS）
CHART_LABEL_LIGHT = QColor("#555555")
CHART_LABEL_DARK = QColor("#cfcfcf")

_DARK_QSS = """
QWidget { background-color: #2b2b2b; color: #dddddd; }
QLineEdit, QComboBox, QSpinBox {
    background-color: #333333; color: #dddddd;
    border: 1px solid #555555; padding: 3px;
}
QComboBox QAbstractItemView {
    background-color: #333333; color: #dddddd;
    selection-background-color: #505050;
}
QTableWidget {
    background-color: #2b2b2b; color: #dddddd;
    gridline-color: #444444;
}
QTableCornerButton::section { background-color: #383838; }
QHeaderView::section {
    background-color: #383838; color: #dddddd;
    border: 1px solid #444444; padding: 4px;
}
QPushButton { background-color: #3c3c3c; border: 1px solid #555555; padding: 4px 12px; }
QPushButton:hover { background-color: #484848; }
QPushButton:pressed { background-color: #2f2f2f; }
QPushButton:disabled { color: #777777; background-color: #333333; }
QMessageBox { background-color: #2b2b2b; }
QMenu { background-color: #333333; color: #dddddd; }
"""


def detect_windows_theme() -> str:
    """读注册表 AppsUseLightTheme：0=深色，非 0/读取失败=浅色。"""
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except OSError:
        return "light"


def stylesheet_for(mode: str) -> str:
    """返回主题样式表；浅色返回空串（Qt 默认）。未知值按浅色处理。"""
    return _DARK_QSS if mode == "dark" else ""


def apply_theme(app: QApplication, mode: str) -> None:
    """应用主题样式表（图表标签色由主窗口同步设置）。"""
    app.setStyleSheet(stylesheet_for(mode))


def chart_label_color(mode: str) -> QColor:
    return CHART_LABEL_DARK if mode == "dark" else CHART_LABEL_LIGHT
