"""用户偏好读写（§3.6）：只记住主题。

2026-10-29 变更：窗口大小/位置与表格排序**不再持久化**——后续 UI 改版时，
旧几何数据会让新布局被挤压甚至窗口跑到屏幕外，旧排序键也可能与新表格列对不上。
现在每次启动都是默认尺寸（1080×760）与「日期降序」。
明确不记住搜索/筛选条件（原 §3.6 约定，未变）。

QSettings 支持 ini 路径注入，测试不碰真实偏好存储。
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from bond_profit.ui import theme

PREFS_ORG = "BondProfit"
PREFS_APP = "BondProfit"

_THEME_KEY = "ui/theme"


def open_settings(ini_path: str | None = None) -> QSettings:
    """打开偏好存储；默认平台存储，测试可注入 ini 文件路径。"""
    if ini_path is not None:
        return QSettings(str(ini_path), QSettings.Format.IniFormat)
    return QSettings(PREFS_ORG, PREFS_APP)


def resolve_theme(settings: QSettings) -> str:
    """解析生效主题：保存过 light/dark 用保存值，否则跟随 Windows。"""
    stored = settings.value(_THEME_KEY, "auto")
    return stored if stored in ("light", "dark") else theme.detect_windows_theme()


def save_theme(settings: QSettings, mode: str) -> None:
    settings.setValue(_THEME_KEY, mode)
