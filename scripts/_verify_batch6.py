"""批次 6 视觉验证：抓四张图 + 数值探针（只写系统临时目录）。"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QApplication

from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.domain.models import SaleRecord
from bond_profit.infrastructure.backup import BackupInfo
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui import theme, tokens
from bond_profit.ui.import_preview_dialog import ImportPreviewDialog
from bond_profit.ui.main_window import MainWindow
from bond_profit.ui.record_dialog import RecordDialog

OUT = Path(tempfile.gettempdir()) / "bp_verify"
OUT.mkdir(exist_ok=True)
STAGE = sys.argv[1] if len(sys.argv) > 1 else "all"


def say(msg: str) -> None:
    with (OUT / "log.txt").open("a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


say(f"=== start stage={STAGE} ===")

app = QApplication(sys.argv[:1])
theme.apply_theme(app, "light")
say("theme ok")

tmp = Path(tempfile.mkdtemp())
conn = connect(tmp / "app.db")
service = SalesService(SalesRepository(conn))
for i, (name, code, price) in enumerate(
    [("平银转债", "127011", "126.00"), ("浦发转债", "110059", "98.50")]
):
    service.create_record(
        SaleRecord(
            bond_name=name,
            bond_code=code,
            sale_date=date(2026, 10, 24 - i),
            sale_price=Decimal(price),
            quantity=10,
            note="上市首日卖出" if i == 0 else "",
        )
    )
excel = ExcelService(service)
say("data ok")

window = MainWindow(service, excel)
window.resize(1080, 760)
window.show()
app.processEvents()
# 主窗口会按持久化偏好自己套一次主题，这里强制到浅色保证可复现
window._apply_theme_mode("light", save=False)
app.processEvents()
say(f"window shown {window.width()}x{window.height()}")


def shot(widget, name: str):
    image = widget.grab().toImage()
    ok = image.save(str(OUT / name))
    say(f"shot {name} {image.width()}x{image.height()} ok={ok}")
    return image


def probe(image, label: str, x: int, y: int) -> None:
    if 0 <= x < image.width() and 0 <= y < image.height():
        say(f"PROBE {label} ({x},{y}) = {image.pixelColor(x, y).name()}")
    else:
        say(f"PROBE {label} ({x},{y}) OUT-OF-RANGE {image.width()}x{image.height()}")


if STAGE in ("all", "data"):
    window.nav_list.setCurrentRow(1)
    app.processEvents()
    img = shot(window, "1-data.png")
    page = window.data_page
    probe(img, "page-canvas", page.mapTo(window, page.rect().topLeft()).x() + 40, 740)
    for child_name in ("import_button", "export_all_button", "export_filtered_button"):
        btn = getattr(page, child_name)
        origin = btn.mapTo(window, btn.rect().topLeft())
        probe(img, f"{child_name}-fill", origin.x() + btn.width() - 8, origin.y() + btn.height() // 2)
        say(f"GEOM {child_name} x={origin.x()} y={origin.y()} w={btn.width()} h={btn.height()}")

if STAGE in ("all", "backup"):
    window.backup_page.populate_backups(
        [
            BackupInfo(
                Path("bondprofit-20261029-0912-auto.db"), "auto", "2026-10-29 09:12", 68, 3, True
            ),
            BackupInfo(
                Path("bondprofit-20261028-2200-manual.db"), "manual", "2026-10-28 22:00", 66, 3, False
            ),
        ]
    )
    window.nav_list.setCurrentRow(2)
    app.processEvents()
    img = shot(window, "2-backup.png")
    btn = window.backup_page.restore_button
    origin = btn.mapTo(window, btn.rect().topLeft())
    probe(img, "danger-border-left", origin.x(), origin.y() + btn.height() // 2)
    probe(img, "danger-fill", origin.x() + btn.width() - 8, origin.y() + btn.height() // 2)
    probe(img, "page-canvas", 700, 720)
    say(
        f"GEOM restore x={origin.x()} y={origin.y()} w={btn.width()} h={btn.height()}"
        f" rows={window.backup_page.table.rowCount()}"
        f" cols={window.backup_page.table.columnCount()}"
    )

if STAGE in ("all", "record"):
    dialog = RecordDialog(service)
    dialog.name_edit.setText("平银转债")
    dialog.price_edit.setText("abc")
    dialog.save_button.click()
    app.processEvents()
    say(f"record errors: {dialog.price_error.text()!r} hidden={dialog.price_error.isHidden()}")
    dialog.show()
    app.processEvents()
    img = shot(dialog, "3-record.png")
    for widget, label in (
        (dialog.price_error, "price-error"),
        (dialog.name_edit, "name-edit"),
        (dialog.quantity_spin, "qty-spin"),
        (dialog.save_button, "save-button"),
    ):
        origin = widget.mapTo(dialog, widget.rect().topLeft())
        probe(img, f"{label}-fill", origin.x() + widget.width() - 8, origin.y() + widget.height() // 2)
        say(f"GEOM {label} x={origin.x()} y={origin.y()} w={widget.width()} h={widget.height()}")
    say(f"GEOM dialog {dialog.width()}x{dialog.height()}")

if STAGE in ("all", "import"):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "卖出记录"
    sheet.append(["转债名称", "转债代码", "卖出日期", "卖出价格", "卖出数量", "备注"])
    sheet.append(["平银转债", "127011", date(2026, 10, 24), Decimal("126.00"), 10, ""])
    sheet.append(["兴业转债", "113052", date(2026, 10, 22), Decimal("120.00"), 10, ""])
    sheet.append(["坏的", "1130", "2026/01/15", Decimal("100.00"), 10, ""])
    xlsx = tmp / "preview.xlsx"
    book.save(xlsx)
    preview = excel.preview_import(str(xlsx))
    say(f"preview new={preview.new_count} dup={preview.duplicate_count} err={preview.error_count}")
    dialog2 = ImportPreviewDialog(excel, preview)
    dialog2.show()
    app.processEvents()
    img = shot(dialog2, "4-import.png")
    for widget, label in (
        (dialog2.status_chip, "chip"),
        (dialog2.confirm_button, "confirm-button"),
    ):
        origin = widget.mapTo(dialog2, widget.rect().topLeft())
        probe(img, f"{label}-fill", origin.x() + widget.width() - 8, origin.y() + widget.height() // 2)
        say(f"GEOM {label} x={origin.x()} y={origin.y()} w={widget.width()} h={widget.height()}")

if STAGE == "dpi":
    # 缩放下的裁切/重叠检查（数值化）：逐层确认子控件都在父容器可视范围内
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    problems = []

    def walk(widget: QWidget) -> None:
        stack = [widget]
        seen = set()
        while stack:
            current = stack.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            for child in current.findChildren(QWidget, "", Qt.FindDirectChildrenOnly):  # 仅直接子级
                stack.append(child)

    say(f"minimumSize={window.minimumSize().width()}x{window.minimumSize().height()}")
    for page_row in (0, 1, 2):
        window.nav_list.setCurrentRow(page_row)
        app.processEvents()
        walk(window)
        say(f"dpi page{page_row} visited")
    dialog = RecordDialog(service)
    dialog.show()
    app.processEvents()
    walk(dialog)
    say("dpi record visited")

    # 第二遍：真正做越界判断
    def check(widget: QWidget) -> None:
        win = widget.window().rect()
        for child in widget.findChildren(QWidget, "", Qt.FindDirectChildrenOnly):
            if not child.isVisible():
                continue
            tl = child.mapTo(widget.window(), child.rect().topLeft())
            br = child.mapTo(widget.window(), child.rect().bottomRight())
            if tl.x() < -2 or tl.y() < -2 or br.x() > win.width() + 2 or br.y() > win.height() + 2:
                problems.append(
                    f"{type(child).__name__}<{child.objectName()}> "
                    f"({tl.x()},{tl.y()})-({br.x()},{br.y()}) 超出 {win.width()}x{win.height()}"
                )
            check(child)

    for page_row in (0, 1, 2):
        window.nav_list.setCurrentRow(page_row)
        app.processEvents()
        check(window)
    dialog.raise_()
    app.processEvents()
    check(dialog)
    for problem in problems[:12]:
        say(f"PROBLEM {problem}")
    say(f"dpi done dpr={window.devicePixelRatioF()} size={window.width()}x{window.height()} problems={len(problems)}")
    raise SystemExit(0)

if STAGE == "compose":
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    names = ["1-data.png", "2-backup.png", "3-record.png", "4-import.png"]
    cells = []
    for name in names:
        image = QImage(str(OUT / name))
        cells.append(image.scaledToWidth(560, Qt.SmoothTransformation))
    col_w = 560
    pad = 10
    rows = [cells[:2], cells[2:]]
    row_h = [max(c.height() for c in row) for row in rows]
    canvas = QImage(col_w * 2 + pad * 3, sum(row_h) + pad * (len(rows) + 1), QImage.Format_RGB32)
    canvas.fill(QColor("#9a9aa2"))
    painter = QPainter(canvas)
    y = pad
    for row, h in zip(rows, row_h):
        x = pad
        for image in row:
            painter.drawImage(x, y, image)
            x += col_w + pad
        y += h + pad
    painter.end()
    canvas.save(str(OUT / "batch6.png"))
    say(f"composed batch6.png {canvas.width()}x{canvas.height()}")
    raise SystemExit(0)

# --- 令牌快照 ---
pal = tokens.palette_for("light")
say(f"tokens line={pal.line} danger={pal.danger} fill={pal.fill} text3={pal.text_3}")

say("=== end ===")
