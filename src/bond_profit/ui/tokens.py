"""设计令牌（Design Tokens）：色值、字号、圆角、控件尺寸的唯一来源。

QSS 由 :mod:`bond_profit.ui.theme` 从本模块生成；图表等自绘控件也从这里取色，
避免出现第二套硬编码色值。改动视觉时只改本文件，不要在下游写死颜色。

硬约束（§3.2 / 验收标准，不可违反）：
- 涨红跌绿：盈利用 ``profit``（红），亏损用 ``loss``（绿），不得反转为欧美习惯。
- 只用系统已装字体、不引入网络字体与图标库，软件保持完全离线。
- 字号统一用 px（不用 pt）：Qt 在高 DPI 下按 devicePixelRatio 统一缩放 px，
  用 pt 会与 px 混算产生半像素错位。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# 系统已装字体栈（2026-10-29 实测可用）。Qt 按顺序取第一个能解析的族，
# 拉丁字形走 Segoe UI Variable Display，中文回退 Microsoft YaHei UI。
FONT_STACK = (
    "Segoe UI Variable Display",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Segoe UI",
)


@dataclass(frozen=True)
class Palette:
    """一套主题的全部色值，字段与提案 B 的 CSS 变量一一对应。"""

    mode: str
    canvas: str  # 主背景
    chrome: str  # 侧栏、状态栏背景
    line: str  # 常规分隔线（行间发丝线）
    line_strong: str  # 表头下边线、输入框聚焦描边
    text: str  # 主文字
    text_2: str  # 次要文字（标签、表头）
    text_3: str  # 弱文字（提示、单位、占位符）
    fill: str  # 输入框、次要按钮底色
    fill_hover: str  # 悬停底色
    accent: str  # 主按钮、tooltip 底色
    accent_fg: str  # 主按钮文字色
    profit: str  # 盈利（红）
    loss: str  # 亏损（绿）
    focus: str  # 焦点环、选中指示条
    selection: str  # 表格行选中/悬停（rgba）
    scroll: str  # 滚动条滑块（rgba）


LIGHT = Palette(
    mode="light",
    canvas="#ffffff",
    chrome="#fbfbfd",
    line="#ececf0",
    line_strong="#dedee3",
    text="#1d1d1f",
    text_2="#6e6e73",
    text_3="#96969c",
    fill="#f4f4f6",
    fill_hover="#ebebef",
    accent="#1d1d1f",
    accent_fg="#ffffff",
    profit="#c62828",
    loss="#2e7d32",
    focus="#0071e3",
    selection="rgba(0, 0, 0, 0.04)",
    scroll="rgba(0, 0, 0, 0.18)",
)

DARK = Palette(
    mode="dark",
    canvas="#121214",
    chrome="#18181a",
    line="#26262a",
    line_strong="#323237",
    text="#f5f5f7",
    text_2="#a1a1a6",
    text_3="#77777e",
    fill="#212124",
    fill_hover="#2a2a2e",
    accent="#f5f5f7",
    accent_fg="#121214",
    profit="#ff6b60",  # 深色下提高亮度，保持红绿语义不变
    loss="#4ade80",
    focus="#0a84ff",
    selection="rgba(255, 255, 255, 0.055)",
    scroll="rgba(255, 255, 255, 0.20)",
)


# 字号阶（px）。hero 是「累计收益」唯一主视觉，其余数值一律降级到 mini。
FONT_SIZE = {
    "tiny": 10,
    "small": 11,
    "body": 12,
    "base": 13,
    "title": 16,
    "mini": 19,
    "hero": 62,
}

# 圆角（px）：卡片 > 控件 > 芯片，保持三级层次。
RADIUS = {
    "card": 9,
    "control": 7,
    "chip": 5,
}

CONTROL_HEIGHT = 28  # 次要按钮、输入框、下拉框统一高度
ROW_HEIGHT = 30  # 表格行高
HEADER_HEIGHT = 26  # 表头高度

SIDEBAR_WIDTH = 196  # 左侧导航宽度（提案 B：图标 + 文字）
NAV_ITEM_HEIGHT = 32  # 导航项行高


def palette_for(mode: str) -> Palette:
    """未知值按浅色处理（与 ``prefs.resolve_theme`` 的容错一致）。"""
    return DARK if mode == "dark" else LIGHT


def apply_app_font(app: QApplication) -> None:
    """设置全局字体族与等宽数字。

    等宽数字（tnum）让表格与统计数字纵向对齐——收益列一水儿的 ``+123.00``
    靠比例数字排出来是歪的，这是「更好地展现数据」最省力的一步。
    字体不支持该特性时静默跳过，不影响显示。
    """
    font = QFont()
    font.setFamilies(list(FONT_STACK))
    font.setPixelSize(FONT_SIZE["base"])
    try:
        font.setFeature(QFont.Tag("tnum"), 1)
    except (AttributeError, TypeError, ValueError):  # 字体或 Qt 版本不支持
        pass
    app.setFont(font)
