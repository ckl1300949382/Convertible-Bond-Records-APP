"""用户偏好读写（§3.6）：主题、窗口大小/位置、表格排序。

记住窗口大小、位置和表头排序；明确不记住搜索/筛选条件。
QSettings 支持 ini 路径注入，测试不碰真实偏好存储。
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings

from bond_profit.ui import theme

PREFS_ORG = "BondProfit"
PREFS_APP = "BondProfit"

_THEME_KEY = "ui/theme"
_GEOMETRY_KEY = "ui/window_geometry"
_SORT_KEY_KEY = "ui/sort_key"
_SORT_DESC_KEY = "ui/sort_desc"

_VALID_SORT_KEYS = ("date", "price", "profit")


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


def load_window_state(settings: QSettings) -> tuple[QByteArray | None, str, bool]:
    """返回 (几何信息, 排序键, 是否降序)；无保存值时用默认。"""
    geometry = settings.value(_GEOMETRY_KEY, None)
    sort_key = settings.value(_SORT_KEY_KEY, "date")
    if sort_key not in _VALID_SORT_KEYS:
        sort_key = "date"
    descending = settings.value(_SORT_DESC_KEY, True, type=bool)
    return geometry, sort_key, descending


def save_window_state(
    settings: QSettings, geometry: QByteArray, sort_key: str, descending: bool
) -> None:
    settings.setValue(_GEOMETRY_KEY, geometry)
    settings.setValue(_SORT_KEY_KEY, sort_key)
    settings.setValue(_SORT_DESC_KEY, descending)
