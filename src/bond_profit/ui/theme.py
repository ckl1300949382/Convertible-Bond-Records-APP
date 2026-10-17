"""主题管理（§3.6 + UI V2.0 阶段 1）：跟随 Windows 浅/深色，手动切换后保存偏好。

V2.0 变化：浅/深两套完整 QSS 由 tokens 调色板生成（浅色不再是 Qt 默认样式），
深色为深海蓝黑 + 冰蓝紫，浅色为珍珠白 + 雾紫蓝；全局字体 Microsoft YaHei UI。
盈亏/错误/图表色统一走令牌：盈利红、亏损绿、零收益中性（中国金融习惯）。
apply_theme 记录最近一次应用的主题，供运行期组件（弹窗、表格前景色等）
通过 active_mode() 查询，避免逐层传递模式参数。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QTextCharFormat
from PySide6.QtWidgets import QApplication, QCalendarWidget

from bond_profit.ui.tokens import (
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_TITLE,
    FONT_SIZE_XL,
    RADIUS_L,
    RADIUS_M,
    RADIUS_S,
    Palette,
    palette_for,
)

# 图表标签色随主题切换（BarChart 自绘，不适用 QSS）
CHART_LABEL_LIGHT = QColor("#5c6478")
CHART_LABEL_DARK = QColor("#a9b7d9")

_CURRENT_MODE = "light"  # 最近一次应用的主题（默认浅色）


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


def active_mode() -> str:
    """最近一次应用的主题（"light"/"dark"）；apply_theme 前默认浅色。"""
    return _CURRENT_MODE


def stylesheet_for(mode: str) -> str:
    """返回主题样式表；未知值按浅色处理。浅/深均为完整定制 QSS。"""
    return _build_qss(palette_for(mode))


def apply_theme(app: QApplication, mode: str) -> None:
    """应用主题样式表 + 全局调色板并记录当前模式（图表色由主窗口同步设置）。

    QSS 不会更新 QPalette：Qt 内部自绘控件（如日历弹层导航栏的月/年按钮）
    按全局调色板绘制文字，深色主题下必须同步设置，否则出现黑字低对比。
    仅同步文字类角色，背景/强调色仍以 QSS 为准，避免全局副作用。
    """
    global _CURRENT_MODE
    _CURRENT_MODE = "dark" if mode == "dark" else "light"
    palette = palette_for(_CURRENT_MODE)
    app.setStyleSheet(stylesheet_for(_CURRENT_MODE))
    app_palette = app.palette()
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.Text,
    ):
        app_palette.setColor(QPalette.ColorGroup.All, role, QColor(palette.text))
    app.setPalette(app_palette)


def chart_label_color(mode: str) -> QColor:
    return CHART_LABEL_DARK if mode == "dark" else CHART_LABEL_LIGHT


def chart_colors(mode: str) -> dict[str, QColor]:
    """图表自绘用色（非 QSS）：零轴线 / 网格 / 盈利红柱 / 亏损绿柱。"""
    palette = palette_for(mode)
    return {
        "axis": QColor(palette.chart_axis),
        "grid": QColor(palette.chart_grid),
        "profit": QColor(palette.profit),
        "loss": QColor(palette.loss),
    }


# ---- 语义色快捷函数（mode 缺省时用当前主题） ---------------------------------


def profit_color(mode: str | None = None) -> QColor:
    """盈利红（中国金融习惯）。"""
    return QColor(palette_for(mode or active_mode()).profit)


def loss_color(mode: str | None = None) -> QColor:
    """亏损绿。"""
    return QColor(palette_for(mode or active_mode()).loss)


def error_color(mode: str | None = None) -> QColor:
    """错误 / 失败提示色。"""
    return QColor(palette_for(mode or active_mode()).danger)


def warning_color(mode: str | None = None) -> QColor:
    """提醒色（如导入预览的「重复跳过」）。"""
    return QColor(palette_for(mode or active_mode()).warning)


def error_qss(mode: str | None = None) -> str:
    """错误文字的内联 QSS（表单错误提示等少数必须内联样式的场景）。"""
    return f"color: {palette_for(mode or active_mode()).danger};"


def apply_calendar_formats(calendar: QCalendarWidget, mode: str | None = None) -> None:
    """日历弹层星期表头随主题配色（UI V2.0 修复深色对比度）。

    星期表头由 QCalendarWidget 内部 weekdayTextFormat 绘制，不走 QSS；
    深色下沿用浅色调色板导致对比度不足。显式设置：周一~周五用弱化文字色，
    周六/周日用主题红（中国日历休息日习惯）。
    导航栏月/年按钮文字色由 apply_theme 的全局调色板统一覆盖。
    """
    palette = palette_for(mode or active_mode())
    fmt_weekday = QTextCharFormat()
    fmt_weekday.setForeground(QColor(palette.text_muted))
    fmt_weekend = QTextCharFormat()
    fmt_weekend.setForeground(QColor(palette.profit))
    for day in (
        Qt.DayOfWeek.Monday,
        Qt.DayOfWeek.Tuesday,
        Qt.DayOfWeek.Wednesday,
        Qt.DayOfWeek.Thursday,
        Qt.DayOfWeek.Friday,
    ):
        calendar.setWeekdayTextFormat(day, fmt_weekday)
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, fmt_weekend)


# ---- QSS 生成 ----------------------------------------------------------------


def _build_qss(p: Palette) -> str:
    """由调色板生成完整 QSS。分节书写，便于按节回退与排查。"""
    return f"""
/* ==== 基础面 ==== */
* {{ font-family: {FONT_FAMILY}; }}
QWidget {{
    background-color: {p.window}; color: {p.text};
    font-size: {FONT_SIZE_BASE}px;
}}
QLabel {{ background: transparent; }}
QToolTip {{
    background-color: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border_strong}; padding: 4px 8px;
}}
QDialog {{ background-color: {p.window}; }}

/* ==== 卡片容器（仅 QFrame 实例；不波及表格等 QFrame 子类） ==== */
.QFrame {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: {RADIUS_M}px;
}}

/* ---- 统计卡（阶段 3；主卡渐变微光 + 强调色描边） ---- */
#statCard {{
    background-color: {p.surface};
    border: 1px solid {p.border}; border-radius: {RADIUS_L}px;
}}
#statCardMain {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {p.surface}, stop:1 {p.accent_tint});
    border: 1px solid {p.accent}; border-radius: {RADIUS_L}px;
}}
#statCardTitle {{ color: {p.text_muted}; font-size: {FONT_SIZE_SM}px; }}
#statCardValue {{ font-size: {FONT_SIZE_XL}px; font-weight: 600; }}

/* ---- 空状态（阶段 3） ---- */
#emptyTitle {{
    color: {p.text}; font-size: {FONT_SIZE_TITLE}px; font-weight: 600;
    background: transparent;
}}
#emptyHint {{ color: {p.text_muted}; background: transparent; }}

/* ---- 二级页标题与提示（阶段 6：数据管理 / 备份与恢复） ---- */
#pageTitle {{ color: {p.text}; font-size: {FONT_SIZE_TITLE}px; font-weight: 600; background: transparent; }}
#pageHint {{ color: {p.text_muted}; background: transparent; }}

/* ==== 输入控件 ==== */
QLineEdit, QComboBox, QSpinBox, QDateEdit {{
    background-color: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border}; border-radius: {RADIUS_S}px;
    padding: 4px 8px; font-size: {FONT_SIZE_MD}px;
    selection-background-color: {p.selection}; selection-color: {p.text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateEdit:disabled {{
    background-color: {p.window}; color: {p.text_muted}; border-color: {p.border};
}}

/* 下拉弹层 */
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-top: 4px solid {p.text_muted}; width: 0; height: 0;
}}
QComboBox QAbstractItemView {{
    background-color: {p.surface}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: {RADIUS_S}px;
    selection-background-color: {p.selection}; selection-color: {p.text};
    outline: 0;
}}

/* 微调框箭头（自定义背景后需自绘箭头） */
QSpinBox::up-button, QDateEdit::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 18px; border: none; background: transparent;
}}
QSpinBox::down-button, QDateEdit::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 18px; border: none; background: transparent;
}}
QSpinBox::up-arrow, QDateEdit::up-arrow {{
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-bottom: 4px solid {p.text_muted}; width: 0; height: 0;
}}
QSpinBox::down-arrow, QDateEdit::down-arrow {{
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-top: 4px solid {p.text_muted}; width: 0; height: 0;
}}
QSpinBox::up-arrow:hover, QDateEdit::up-arrow:hover {{ border-bottom-color: {p.accent}; }}
QSpinBox::down-arrow:hover, QDateEdit::down-arrow:hover {{ border-top-color: {p.accent}; }}

/* ==== 按钮 ==== */
QPushButton {{
    background-color: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border}; border-radius: {RADIUS_S}px;
    padding: 5px 14px; font-size: {FONT_SIZE_BASE}px;
}}
QPushButton:hover {{ background-color: {p.hover_bg}; border-color: {p.border_strong}; }}
QPushButton:pressed {{ background-color: {p.pressed_bg}; }}
/* 默认按钮（弹窗/消息框的确认键，阶段 4）：强调色文字描边，不抢 accent 主按钮底色。
   须置于 [accent] 与 :disabled 规则之前，保证 accent 主按钮与禁用态优先。 */
QPushButton:default {{ color: {p.accent}; border-color: {p.accent}; font-weight: 600; }}
QPushButton:disabled {{
    color: {p.text_muted}; background-color: {p.surface_alt};
    border-color: {p.border};
}}
/* 主操作按钮（阶段 2 工具栏启用，property accent=true） */
QPushButton[accent="true"] {{
    background-color: {p.accent}; color: {p.accent_text};
    border: 1px solid {p.accent}; font-weight: 600;
}}
QPushButton[accent="true"]:hover {{ background-color: {p.accent_hover}; }}
QPushButton[accent="true"]:pressed {{ background-color: {p.accent_pressed}; }}
QPushButton[accent="true"]:disabled {{
    background-color: {p.surface_alt}; color: {p.text_muted};
    border-color: {p.border}; font-weight: 400;
}}

/* ==== 表格 ==== */
QTableWidget {{
    background-color: {p.surface}; color: {p.text};
    border: 1px solid {p.border}; border-radius: {RADIUS_S}px;
    gridline-color: {p.gridline};
    selection-background-color: {p.selection}; selection-color: {p.text};
    alternate-background-color: {p.zebra};
}}
QTableWidget::item:hover {{ background-color: {p.hover_bg}; }}
QTableCornerButton::section {{ background-color: {p.surface_alt}; border: none; }}
QHeaderView::section {{
    background-color: {p.surface_alt}; color: {p.text_muted};
    border: none; border-bottom: 1px solid {p.border};
    padding: 6px 8px; font-weight: 600;
}}

/* ==== 滚动条 ==== */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {p.border_strong}; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {p.border_strong}; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {p.text_muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ==== 列表（左侧导航） ==== */
QListWidget {{
    background-color: {p.surface}; border: 1px solid {p.border};
    border-radius: {RADIUS_M}px; padding: 6px; outline: 0;
    font-size: {FONT_SIZE_MD}px;
}}
QListWidget::item {{
    color: {p.text_muted}; border-radius: {RADIUS_S}px;
    padding: 8px 12px; margin: 2px 0;
}}
QListWidget::item:hover {{ background: {p.hover_bg}; color: {p.text}; }}
QListWidget::item:selected {{
    background: {p.accent_tint}; color: {p.accent}; font-weight: 600;
}}

/* ---- 侧边导航强化（主窗口 #navSidebar；选中项加强调色指示条） ---- */
#navSidebar::item {{ padding: 9px 12px; margin: 3px 6px; }}
#navSidebar::item:selected {{
    background: {p.accent_tint}; color: {p.accent};
    border-left: 3px solid {p.accent}; padding-left: 9px;
    font-weight: 600;
}}

/* ==== 菜单 / 消息框 / 状态栏 ==== */
QMenu {{
    background-color: {p.surface}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {p.selection}; }}
QMessageBox {{ background-color: {p.surface}; }}
QStatusBar {{
    background: {p.surface}; color: {p.text_muted};
    border-top: 1px solid {p.border};
}}

/* ==== 日历弹层（QDateEdit calendarPopup） ==== */
QCalendarWidget QWidget {{ alternate-background-color: {p.surface_alt}; }}
QCalendarWidget QToolButton {{
    background-color: {p.surface_alt}; color: {p.text};
    border-radius: {RADIUS_S}px; padding: 4px 8px;
}}
QCalendarWidget QToolButton:hover {{ background-color: {p.hover_bg}; }}
QCalendarWidget QSpinBox {{
    background-color: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border};
}}
QCalendarWidget QAbstractItemView {{
    background-color: {p.surface}; color: {p.text};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
    outline: 0;
}}
QCalendarWidget #qt_calendar_navigationbar {{ background-color: {p.surface_alt}; }}
QCalendarWidget #qt_calendar_monthbutton,
QCalendarWidget #qt_calendar_yearbutton {{ color: {p.text}; background: transparent; }}
QCalendarWidget #qt_calendar_calendarview {{ background-color: {p.surface}; }}
"""
