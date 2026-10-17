"""UI V2.0 设计令牌：颜色、字体、间距、圆角集中定义（UI V2.0 阶段 1）。

深色 = 深海蓝黑背景 + 冰蓝紫强调，现代科技金融风格；
浅色 = 珍珠白背景 + 雾紫蓝强调，精致轻奢风格。
盈亏颜色遵循中国金融习惯：盈利红、亏损绿、零收益中性。
两种模式各调亮度保证对比度。

约定：界面代码禁止再硬编码十六进制色值，一律引用本模块（或经 theme 间接引用）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """一套主题的全部颜色令牌（QSS 十六进制/rgba 字符串）。"""

    # ---- 基础面 ----
    window: str  # 窗口背景
    surface: str  # 卡片 / 面板
    surface_alt: str  # 次级面（输入框、表头、按钮）
    hover_bg: str  # 控件悬浮背景
    pressed_bg: str  # 控件按下背景
    border: str  # 常规边框
    border_strong: str  # 强边框（悬浮、弹层）

    # ---- 文本 ----
    text: str  # 主文本
    text_muted: str  # 次要文本 / 标签

    # ---- 强调色 ----
    accent: str  # 强调色
    accent_hover: str
    accent_pressed: str
    accent_text: str  # 强调色背景上的文字
    accent_tint: str  # 强调色低透明度底（选中态染色）

    # ---- 语义色（盈亏遵循中国金融习惯：盈利红 / 亏损绿） ----
    profit: str  # 盈利红
    loss: str  # 亏损绿
    danger: str  # 错误 / 失败
    warning: str  # 提醒（如「重复跳过」）

    # ---- 表格 ----
    gridline: str  # 表格网格线
    zebra: str  # 斑马纹（备用）
    selection: str  # 列表/表格选中背景（弱强调，保持文字可读）

    # ---- 图表 ----
    chart_axis: str  # 零轴线
    chart_grid: str  # 网格线


DARK = Palette(
    window="#0e1524",
    surface="#141d31",
    surface_alt="#1b2540",
    hover_bg="#223052",
    pressed_bg="#18223c",
    border="#27334f",
    border_strong="#384a72",
    text="#dde5f4",
    text_muted="#8291b4",
    accent="#7b9bff",
    accent_hover="#93adff",
    accent_pressed="#5d7fe8",
    accent_text="#0b1120",
    accent_tint="rgba(123, 155, 255, 0.16)",
    profit="#ff5d5d",
    loss="#34c38f",
    danger="#ff6b6b",
    warning="#e6b35a",
    gridline="#223052",
    zebra="#121a2c",
    selection="#2c3e66",
    chart_axis="#465a85",
    chart_grid="#1d2742",
)

LIGHT = Palette(
    window="#f7f6fb",
    surface="#ffffff",
    surface_alt="#eff0f7",
    hover_bg="#e6e8f5",
    pressed_bg="#dde0f0",
    border="#e0e2ee",
    border_strong="#c9cde0",
    text="#2b3040",
    text_muted="#6e7688",
    accent="#6b79d6",
    accent_hover="#7c89e0",
    accent_pressed="#5563c2",
    accent_text="#ffffff",
    accent_tint="rgba(107, 121, 214, 0.10)",
    profit="#c62828",
    loss="#2e7d32",
    danger="#c62828",
    warning="#b07a00",
    gridline="#e7e9f2",
    zebra="#f8f8fc",
    selection="#dfe3f9",
    chart_axis="#b9bfd0",
    chart_grid="#e8eaf3",
)


def palette_for(mode: str) -> Palette:
    """按主题名返回调色板；未知值按浅色处理（与 theme.stylesheet_for 一致）。"""
    return DARK if mode == "dark" else LIGHT


# ---- 字体排版 -----------------------------------------------------------------

FONT_FAMILY = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'
FONT_SIZE_SM = 11  # 辅助说明
FONT_SIZE_BASE = 12  # 正文 / 控件
FONT_SIZE_MD = 13  # 输入框
FONT_SIZE_TITLE = 18  # 页面标题
FONT_SIZE_XL = 20  # 统计卡数值（阶段 3 使用）

# ---- 间距 / 圆角（布局代码使用，单位 px） -------------------------------------

SPACE_S = 6
SPACE_M = 10
SPACE_L = 16
SPACE_XL = 24

RADIUS_S = 6
RADIUS_M = 10
RADIUS_L = 14
