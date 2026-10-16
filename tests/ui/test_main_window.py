"""主窗口 UI 测试（pytest-qt）。"""

from __future__ import annotations

import bond_profit
from bond_profit.ui.main_window import MainWindow


def test_window_creates_shows_and_closes(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()
    assert window.windowTitle() == f"可转债收益记录 v{bond_profit.__version__}"

    window.close()
    assert not window.isVisible()
    # qtbot.addWidget 负责测试结束后的组件清理
