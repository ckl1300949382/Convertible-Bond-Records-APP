"""应用装配与启动。

负责：日志初始化、单实例控制（§3.6）、数据库与服务装配、显示主窗口。
"""

from __future__ import annotations

import logging
import sys

import bond_profit
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from bond_profit.application.sales_service import SalesService
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.logging import setup_logging
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.main_window import MainWindow

logger = logging.getLogger(__name__)

_SINGLE_INSTANCE_KEY = "BondProfit-SingleInstance"


def main() -> int:
    setup_logging()
    logger.info("应用启动，版本 %s", bond_profit.__version__)

    app = QApplication(sys.argv)
    app.setApplicationName("可转债收益记录")
    app.setOrganizationName("BondProfit")

    if _is_another_instance_running():
        logger.info("检测到已有实例运行，通知其激活窗口后退出")
        _notify_existing_instance()
        return 0

    conn = connect()
    service = SalesService(SalesRepository(conn))

    window = MainWindow(service)
    _start_single_instance_server(window)

    window.show()
    return app.exec()


# ---- 单实例（文档 §3.6） ----------------------------------------------------


def _is_another_instance_running(key: str = _SINGLE_INSTANCE_KEY) -> bool:
    """尝试连接已有实例的本地服务；连得上说明已在运行。"""
    socket = QLocalSocket()
    socket.connectToServer(key)
    running = socket.waitForConnected(200)
    if running:
        socket.disconnectFromServer()
    return running


def _notify_existing_instance(key: str = _SINGLE_INSTANCE_KEY) -> None:
    socket = QLocalSocket()
    socket.connectToServer(key)
    if socket.waitForConnected(200):
        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()


def _start_single_instance_server(
    window: MainWindow, key: str = _SINGLE_INSTANCE_KEY
) -> QLocalServer:
    """监听本地服务；后续实例启动时通知本实例激活窗口。

    Windows 命名管道随进程退出自动清理，removeServer 处理异常残留（跨平台惯例）。
    """
    QLocalServer.removeServer(key)
    server = QLocalServer()
    server.listen(key)

    def _on_new_connection() -> None:
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.readAll()
            conn.disconnectFromServer()
        window.setWindowState(
            (window.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        window.raise_()
        window.activateWindow()

    server.newConnection.connect(_on_new_connection)
    return server
