"""应用装配与启动。

阶段 0 仅负责：初始化日志、创建 QApplication、显示最小主窗口。
单实例控制按文档安排在阶段 1 实现。
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from bond_profit.infrastructure.logging import setup_logging
from bond_profit.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def main() -> int:
    setup_logging()
    logger.info("应用启动，版本 %s", __import__("bond_profit").__version__)

    app = QApplication(sys.argv)
    app.setApplicationName("可转债收益记录")
    app.setOrganizationName("BondProfit")

    window = MainWindow()
    window.show()
    return app.exec()
