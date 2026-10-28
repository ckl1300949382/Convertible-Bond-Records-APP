"""主题管理（§3.6）：跟随 Windows 浅/深色，手动切换后保存偏好。

浅色与深色都由 :mod:`bond_profit.ui.tokens` 的令牌生成完整 QSS——
浅色不再是「空样式退回 Qt 默认」，两套主题走同一条渲染路径。

QSS 书写规则（踩过的坑，必须遵守）：
- 禁止裸 ``QWidget { ... }`` 选择器：它会污染所有子控件，把卡片/输入框全变成灰块。
  需要背景时用 ``objectName``（``#root``）或具体类型选择器。
- 强制 Fusion 风格：Windows 原生 style 会忽略部分 QSS（圆角、扁平按钮），
  只有 Fusion 能稳定按样式表渲染。
"""

from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from bond_profit.ui import tokens

# QSS 模板：占位符与 Palette 字段同名，由 tokens.palette_for(mode) 填充。
_TEMPLATE = Template(
    """
/* ---- 基础面 ---- */
QMainWindow, QDialog, QMessageBox {
    background-color: $canvas;
}
QWidget#root {
    background-color: $canvas;
}
QLabel, QCheckBox, QRadioButton, QGroupBox {
    background: transparent;
    color: $text;
}

/* ---- 按钮：默认扁平，悬停才出现底色（对应提案 B 的次要按钮） ---- */
QPushButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: ${radius_control}px;
    color: $text_2;
    font-size: ${f_body}px;
    min-height: ${control_h}px;
    padding: 0 10px;
}
QPushButton:hover {
    background-color: $fill;
    color: $text;
}
QPushButton:pressed {
    background-color: $fill_hover;
}
QPushButton:disabled {
    background: transparent;
    color: $text_3;
}
QPushButton:default {
    background-color: $accent;
    border-color: $accent;
    color: $accent_fg;
    font-weight: 500;
}
QPushButton:default:hover {
    background-color: $accent;
    color: $accent_fg;
}

/* ---- 输入类控件 ---- */
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background-color: $fill;
    border: 1px solid transparent;
    border-radius: ${radius_control}px;
    color: $text;
    font-size: ${f_body}px;
    min-height: ${control_h}px;
    padding: 0 8px;
    selection-background-color: $focus;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    background-color: $canvas;
    border-color: $line_strong;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateEdit:disabled {
    background-color: $fill;
    color: $text_3;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox QAbstractItemView {
    background-color: $canvas;
    border: 1px solid $line_strong;
    border-radius: ${radius_control}px;
    color: $text;
    font-size: ${f_body}px;
    outline: none;
    padding: 4px;
    selection-background-color: $fill;
    selection-color: $text;
}

/* ---- 表格 ---- */
QTableWidget {
    background-color: $canvas;
    alternate-background-color: $canvas;
    border: none;
    color: $text;
    font-size: ${f_body}px;
    gridline-color: $line;
    outline: none;
    selection-background-color: $selection;
    selection-color: $text;
}
QTableWidget::item {
    padding: 0 8px;
}
QTableWidget::item:selected {
    background-color: $selection;
    color: $text;
}
QHeaderView {
    background: transparent;
    border: none;
    font-size: ${f_small}px;
}
QHeaderView::section {
    background-color: $canvas;
    border: none;
    border-bottom: 1px solid $line_strong;
    color: $text_3;
    font-size: ${f_small}px;
    padding: 4px 8px;
}
QHeaderView::section:hover {
    color: $text_2;
}
QTableCornerButton::section {
    background-color: $canvas;
    border: none;
}

/* ---- 左侧导航 ---- */
QListWidget {
    background-color: $chrome;
    border: none;
    border-right: 1px solid $line;
    font-size: ${f_body}px;
    outline: none;
    padding: 10px 8px;
}
QListWidget::item {
    border-radius: ${radius_control}px;
    color: $text_2;
    margin-bottom: 2px;
    padding: 8px 9px;
}
QListWidget::item:hover {
    background-color: $fill_hover;
    color: $text;
}
QListWidget::item:selected {
    background-color: $canvas;
    border: 1px solid $line_strong;
    color: $text;
    font-weight: 500;
}

/* ---- 滚动条：默认隐形，悬停显形 ---- */
QScrollBar:vertical {
    background: transparent;
    border: none;
    margin: 0;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: $scroll;
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: $text_3;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    border: none;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: $scroll;
    border-radius: 5px;
    min-width: 28px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ---- 状态栏、提示、菜单 ---- */
QStatusBar {
    background-color: $chrome;
    border-top: 1px solid $line;
    color: $text_3;
    font-size: ${f_small}px;
}
QStatusBar::item {
    border: none;
}
QToolTip {
    background-color: $accent;
    border: none;
    border-radius: ${radius_chip}px;
    color: $accent_fg;
    font-size: ${f_small}px;
    padding: 4px 8px;
}
QMenu {
    background-color: $canvas;
    border: 1px solid $line_strong;
    border-radius: ${radius_control}px;
    color: $text;
    font-size: ${f_body}px;
    padding: 4px;
}
QMenu::item {
    border-radius: ${radius_chip}px;
    padding: 6px 18px;
}
QMenu::item:selected {
    background-color: $fill;
    color: $text;
}

/* ---- 日期弹层（QDateEdit 的日历不受父级 QSS 控制，需单独着色） ---- */
QCalendarWidget QWidget {
    background-color: $canvas;
    color: $text;
}
QCalendarWidget QAbstractItemView {
    background-color: $canvas;
    color: $text;
    selection-background-color: $accent;
    selection-color: $accent_fg;
}
QCalendarWidget QToolButton {
    background: transparent;
    color: $text;
}
"""
)


def _substitutions(mode: str) -> dict[str, str]:
    """把令牌摊平成模板占位符（Palette 字段同名直取）。"""
    palette = tokens.palette_for(mode)
    values = {
        field: getattr(palette, field) for field in palette.__dataclass_fields__
    }
    values["radius_control"] = str(tokens.RADIUS["control"])
    values["radius_chip"] = str(tokens.RADIUS["chip"])
    values["control_h"] = str(tokens.CONTROL_HEIGHT)
    values["f_small"] = str(tokens.FONT_SIZE["small"])
    values["f_body"] = str(tokens.FONT_SIZE["body"])
    return values


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
    """返回该主题的完整 QSS；未知值按浅色处理。"""
    return _TEMPLATE.substitute(_substitutions(mode))


# 只有 Fusion 会严格按 QSS 渲染（原生 Windows 风格会吃掉圆角与扁平按钮）。
# 设过一次就在 QApplication 上打标记，避免每次切主题都重建风格对象。
BASE_STYLE = "Fusion"
BASE_STYLE_MARK = "bpBaseStyle"


def _ensure_base_style(app: QApplication) -> None:
    if app.property(BASE_STYLE_MARK):
        return
    app.setStyle(BASE_STYLE)
    app.setProperty(BASE_STYLE_MARK, True)


def apply_theme(app: QApplication, mode: str) -> None:
    """应用主题：Fusion 风格 + 全局字体 + 由令牌生成的 QSS。"""
    _ensure_base_style(app)
    tokens.apply_app_font(app)
    app.setStyleSheet(stylesheet_for(mode))


def chart_label_color(mode: str) -> QColor:
    """自绘图表的标签/轴线颜色（BarChart 不吃 QSS，需显式同步）。

    用 text_2 而非 text_3：图表标签只有 9–10px，深色下 text_3 对比度不足。
    """
    return QColor(tokens.palette_for(mode).text_2)
