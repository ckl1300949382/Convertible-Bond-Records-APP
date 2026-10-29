"""内联 SVG 图标库：不引入图标字体、不联网，全部矢量自绘并用 QSvgRenderer 渲染。

Qt 的 SVG 渲染不解析 CSS 的 ``currentColor``，所以图元里留 ``{color}`` 占位符，
由 :func:`svg_for` / :func:`icon` 把当前主题色注入 ``stroke``，随主题切换重新取色。

图标统一按 20×20 画布设计（与提案 B 一致），线宽 1.6、圆角端点，
保证三个导航图标与工具栏图标视觉粗细一致。
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# 图元：只放 path/rect/circle 等基本形状，外套属性在 _wrap 里统一给出。
_GLYPHS: dict[str, str] = {
    # 总览：四宫格
    "overview": (
        '<rect x="2.6" y="2.6" width="6" height="6" rx="1.6"/>'
        '<rect x="11.4" y="2.6" width="6" height="6" rx="1.6"/>'
        '<rect x="2.6" y="11.4" width="6" height="6" rx="1.6"/>'
        '<rect x="11.4" y="11.4" width="6" height="6" rx="1.6"/>'
    ),
    # 数据管理：导入到盘（向下箭头 + 托盘）
    "data": (
        '<path d="M10 2.8v8.4"/>'
        '<path d="M6.8 8.2L10 11.4l3.2-3.2"/>'
        '<path d="M3.2 13.4v2.4a1.4 1.4 0 001.4 1.4h10.8a1.4 1.4 0 001.4-1.4v-2.4"/>'
    ),
    # 备份与恢复：盾牌 + 勾
    "backup": (
        '<path d="M10 2.8l6.2 2.5v5c0 3.5-2.6 5.8-6.2 6.9-3.6-1.1-6.2-3.4-6.2-6.9v-5L10 2.8z"/>'
        '<path d="M7.4 9.9l1.8 1.8 3.4-3.5"/>'
    ),
    "plus": '<path d="M10 4.6v10.8M4.6 10h10.8"/>',
    "pencil": (
        '<path d="M13.6 3.4l3 3L7 16H4v-3L13.6 3.4z"/>'
        '<path d="M12.2 4.8l3 3"/>'
    ),
    "trash": (
        '<path d="M3.6 6h12.8"/>'
        '<path d="M8 6V4.3h4V6"/>'
        '<path d="M5.6 6l.8 10.1a1 1 0 001 .9h5.2a1 1 0 001-.9L14.4 6"/>'
    ),
    "search": (
        '<circle cx="9" cy="9" r="5.6"/>'
        '<path d="M13.2 13.2L17 17"/>'
    ),
    "sun": (
        '<circle cx="10" cy="10" r="3.6"/>'
        '<path d="M10 2.4v1.7M10 15.9v1.7M2.4 10h1.7M15.9 10h1.7"/>'
        '<path d="M4.7 4.7l1.2 1.2M14.1 14.1l1.2 1.2"/>'
        '<path d="M15.3 4.7l-1.2 1.2M5.9 14.1l-1.2 1.2"/>'
    ),
    "moon": (
        '<path d="M15.8 12.4A6.4 6.4 0 017.6 4.2a6.6 6.6 0 108.2 8.2z"/>'
    ),
    # 文件夹（打开日志）
    "folder": (
        '<path d="M2.8 6.2a1.4 1.4 0 011.4-1.4h3l1.6 2h6.8a1.4 1.4 0 011.4 1.4v7.2a1.4 1.4 0 01-1.4 1.4H4.2a1.4 1.4 0 01-1.4-1.4V6.2z"/>'
    ),
    # 刷新
    "refresh": (
        '<path d="M16.2 8.4A6.4 6.4 0 004.6 6.2L2.8 8"/>'
        '<path d="M2.8 4v4h4"/>'
        '<path d="M3.8 11.6a6.4 6.4 0 0011.6 2.2l1.8-1.8"/>'
        '<path d="M17.2 16v-4h-4"/>'
    ),
    # 勾（备份完好）
    "check": '<path d="M4.5 10.5l3.4 3.4 7.6-8"/>',
    # 警告（备份异常）
    "alert": (
        '<path d="M10 3.2l7 12.4H3L10 3.2z"/>'
        '<path d="M10 8v3.4"/>'
        '<path d="M10 13.6v.6"/>'
    ),
}

_STROKE_WIDTH = 1.6


def svg_for(name: str, color: str, size: int = 16) -> str:
    """拼出完整 SVG 字符串；未登记的名字返回空 ``<svg>``（调用方会得到空图标）。"""
    body = _GLYPHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 20 20" fill="none" stroke="{color}" '
        f'stroke-width="{_STROKE_WIDTH}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


@lru_cache(maxsize=256)
def _svg_bytes(name: str, color: str, size: int) -> bytes:
    """缓存拼好的 SVG 字节串。

    只缓存字符串、不缓存 ``QPixmap``：``QPixmap`` 绑定 ``QApplication``，
    测试里重建 app 后旧位图会变成悬空对象，极易段错误。
    """
    return svg_for(name, color, size).encode("utf-8")


def _render(name: str, color: str, size: int, dpr: int) -> QPixmap:
    """按设备像素比渲染成位图。"""
    renderer = QSvgRenderer(QByteArray(_svg_bytes(name, color, size)))
    pixmap = QPixmap(size * dpr, size * dpr)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def icon(name: str, color: str, size: int = 16, dpr: int = 2) -> QIcon:
    """取一个按 ``color`` 着色的图标，用于按钮、导航项等。

    不随 DPI 自动重绘——``dpr=2`` 的位图在 100%/125%/150% 下缩放都足够清晰，
    避免为此引入自绘 ``QIconEngine``。
    """
    return QIcon(_render(name, color, size, dpr))


def pixmap(name: str, color: str, size: int = 16, dpr: int = 2) -> QPixmap:
    """取图标位图，用于需要直接贴图的场合（如自绘图表里的提示图标）。"""
    return _render(name, color, size, dpr)
