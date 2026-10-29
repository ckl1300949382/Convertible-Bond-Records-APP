"""把 assets/app-icon.svg 渲染成多尺寸 PNG 并打包成 Windows .ico。

用法：.venv\\Scripts\\python scripts\\build_app_icon.py
产物：assets/app-icon.ico（16/32/48/256）、assets/app-icon-512.png（预览）

设计取舍：16/32 两档用「加粗版」（柱子更粗、去掉弱横线），
因为小尺寸下 52px 宽的柱子和 0.16 透明度的横线会糊成灰雾。
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = ROOT / "assets" / "app-icon.svg"

# 加粗版（小尺寸专用）：柱宽 96 / 间距 32，顶部圆角 48，弱横线置零
COMPACT_BARS = [
    '<path d="M80 384 V 264 A 48 48 0 0 1 176 264 V 384 Z" fill="url(#bar)"/>',
    '<path d="M208 384 V 184 A 48 48 0 0 1 304 184 V 384 Z" fill="url(#bar)"/>',
    '<path d="M336 384 V 104 A 48 48 0 0 1 432 104 V 384 Z" fill="url(#bar)"/>',
]
FULL_BARS = [
    '<path d="M152 384 V 302 A 26 26 0 0 1 204 302 V 384 Z" fill="url(#bar)"/>',
    '<path d="M230 384 V 234 A 26 26 0 0 1 282 234 V 384 Z" fill="url(#bar)"/>',
    '<path d="M308 384 V 154 A 26 26 0 0 1 360 154 V 384 Z" fill="url(#bar)"/>',
]


def make_compact(svg: str) -> str:
    out = svg
    for full, compact in zip(FULL_BARS, COMPACT_BARS):
        out = out.replace(full, compact)
    out = out.replace('fill-opacity="0.16"', 'fill-opacity="0"')
    out = out.replace('y="384" width="240" height="6" rx="3"', 'y="380" width="240" height="10" rx="5"')
    return out


def render(svg: str, size: int) -> bytes:
    renderer = QSvgRenderer(svg.encode("utf-8"))
    if not renderer.isValid():
        raise SystemExit("SVG 无法解析")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = bytearray()
    from PySide6.QtCore import QBuffer, QByteArray

    byte_array = QByteArray()
    qbuffer = QBuffer(byte_array)
    qbuffer.open(QBuffer.WriteOnly)
    image.save(qbuffer, "PNG")
    qbuffer.close()
    buffer = bytes(byte_array.data())
    return buffer


def pack_ico(entries: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = b""
    blobs = b""
    for size, data in entries:
        directory += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0,
            0,
            1,
            32,
            len(data),
            offset,
        )
        blobs += data
        offset += len(data)
    return header + directory + blobs


def main() -> None:
    svg = SVG_PATH.read_text(encoding="utf-8")
    compact = make_compact(svg)

    entries: list[tuple[int, bytes]] = []
    for size in (16, 32):
        entries.append((size, render(compact, size)))
    for size in (48, 256):
        entries.append((size, render(svg, size)))

    ico_path = ROOT / "assets" / "app-icon.ico"
    ico_path.write_bytes(pack_ico(entries))

    preview = render(svg, 512)
    png_path = ROOT / "assets" / "app-icon-512.png"
    png_path.write_bytes(preview)

    # 多尺寸预览（浅底 + 深底两行），人工核对小尺寸可辨识度
    # 注意：本环境里 QFont/drawText 会让进程静默退出，预览图不放文字标注
    from PySide6.QtGui import QColor

    W, H = 920, 460
    sheet = QImage(W, H, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#ffffff"))
    painter = QPainter(sheet)
    painter.fillRect(0, 230, W, 230, QColor("#121214"))
    x = 40
    for size, source in ((256, svg), (128, svg), (48, svg), (32, compact), (16, compact)):
        icon = QImage()
        icon.loadFromData(render(source, size), "PNG")
        painter.drawImage(x, 115 - size // 2, icon)
        painter.drawImage(x, 345 - size // 2, icon)
        x += size + 40
    painter.end()
    sheet_path = ROOT / "assets" / "app-icon-preview.png"
    sheet.save(str(sheet_path), "PNG")

    # 数值抽检：底为墨色、柱为红色、四角透明
    image = QImage()
    image.loadFromData(preview, "PNG")
    print("512 预览：", image.width(), "x", image.height())
    print("  磁贴中心底色 =", image.pixelColor(256, 60).name())
    print("  最高柱中段   =", image.pixelColor(334, 250).name())
    print("  最低柱中段   =", image.pixelColor(178, 350).name())
    print("  左上角(外部) alpha =", image.pixelColor(2, 2).alpha())
    print("已生成：", ico_path.relative_to(ROOT), f"{ico_path.stat().st_size} B")
    print("已生成：", png_path.relative_to(ROOT), f"{png_path.stat().st_size} B")
    return None


if __name__ == "__main__":
    sys.exit(main())
