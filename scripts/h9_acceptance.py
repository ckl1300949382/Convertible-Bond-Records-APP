"""H9 人工验收脚本（阶段 5）：真实 UI 全流程「手动备份 → 自动备份列表 → 恢复并核对统计」。

运行：.venv\\Scripts\\python.exe scripts\\h9_acceptance.py
使用真实业务代码与真实 UI 组件（非测试桩），仅数据目录注入临时路径，
不影响本机 %LOCALAPPDATA% 真实数据。
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from bond_profit.application.backup_service import BackupService
from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.domain.models import SaleRecord
from bond_profit.infrastructure.backup_state import StateStore
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.main_window import MainWindow


def _rec(name: str, code: str, price: str, qty: int) -> SaleRecord:
    return SaleRecord(
        bond_name=name,
        bond_code=code,
        sale_date=date(2026, 1, 15),
        sale_price=Decimal(price),
        quantity=qty,
        note="",
    )


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="h9_accept_"))
    app = QApplication([])

    # 全程屏蔽模态弹窗（沙箱无人值守），仅保留流程断言
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    conn = connect(root / "data" / "app.db")
    backup = BackupService(
        conn,
        StateStore(root / "state.json"),
        root / "backups" / "auto",
        root / "backups" / "protected",
    )
    service = SalesService(SalesRepository(conn), on_change=backup.mark_dirty)
    window = MainWindow(service, ExcelService(service), backup_service=backup)
    window.show()

    # [1] 录入两条记录，记录基准统计
    service.create_record(_rec("H9验收甲", "111111", "130.00", 10))
    service.create_record(_rec("H9验收乙", "222222", "95.00", 20))
    window.refresh_records()
    base_profit = window.total_profit_value.text()
    print(f"[1] 录入2条记录，累计收益卡片 = {base_profit!r}，表格行数 = {window.table.rowCount()}")

    # [2] 点「手动备份到…」（真实按钮信号），备份文件落入自选目录
    manual_dir = root / "手动备份目录"
    manual_dir.mkdir()
    window.backup_page.manual_backup_requested.emit(str(manual_dir))
    manual_files = list(manual_dir.glob("app_*.db"))
    assert len(manual_files) == 1, manual_files
    print(f"[2] 手动备份已生成：{manual_files[0].name}")

    # [3] 产生一份自动备份（真实策略路径：置脏后检查），查看备份列表
    backup.mark_dirty()
    assert backup.run_auto_backup() is not None
    window._refresh_backup_list()
    rows = window.backup_page.table.rowCount()
    kinds = [window.backup_page.table.item(r, 1).text() for r in range(rows)]
    print(f"[3] 备份列表 {rows} 行，类型 = {kinds}（手动备份在自选目录不入列，属已批准决策②）")
    assert rows == 1 and kinds == ["自动"]

    # [4] 数据变更：新增第三条，统计应变化
    service.create_record(_rec("H9验收丙", "333333", "120.00", 5))
    window.refresh_records()
    changed_profit = window.total_profit_value.text()
    print(f"[4] 新增第3条后，累计收益卡片 = {changed_profit!r}")
    assert changed_profit != base_profit

    # [5] 在列表中选择备份恢复（确认对话框已置 Yes），核对数据与统计回到备份时点
    window.backup_page.table.selectRow(0)
    window.backup_page.restore_button.click()
    names = [r.bond_name for r in service.list_records()]
    restored_profit = window.total_profit_value.text()
    print(f"[5] 恢复后记录 = {names}，总览表格行数 = {window.table.rowCount()}")
    print(f"[5] 恢复后累计收益卡片 = {restored_profit!r}（应回到基准）")
    assert sorted(names) == ["H9验收乙", "H9验收甲"]  # 同日期按创建时间倒序，不假设顺序
    assert window.table.rowCount() == 2
    assert restored_profit == base_profit

    # [6] 恢复前保护备份已自动创建
    protected = list((root / "backups" / "protected").glob("app_*.db"))
    print(f"[6] 恢复前保护备份数 = {len(protected)}")
    assert len(protected) == 1

    conn.close()
    print("H9 人工验收（脚本化执行，真实 UI）全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
