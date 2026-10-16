"""主窗口。阶段 0 仅提供最小骨架界面。"""

from __future__ import annotations

import bond_profit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"可转债收益记录 v{bond_profit.__version__}")
        self.resize(960, 640)

        placeholder = QLabel("阶段 0：工程骨架已就绪")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
