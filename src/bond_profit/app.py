"""应用装配与启动。

负责：日志初始化、单实例控制（§3.6）、数据库与服务装配、显示主窗口。
"""

from __future__ import annotations

import logging
import sqlite3
import sys

import bond_profit
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from bond_profit.application.backup_service import BackupService
from bond_profit.application.excel_service import ExcelService
from bond_profit.application.sales_service import SalesService
from bond_profit.infrastructure.backup import BackupError, backup_dirs, create_backup
from bond_profit.infrastructure.backup_state import StateStore
from bond_profit.infrastructure.database import (
    SCHEMA_VERSION,
    DatabaseCorruptError,
    DatabaseTooNewError,
    MigrationError,
    connect,
    default_database_path,
    inspect_database,
)
from bond_profit.infrastructure.logging import setup_logging
from bond_profit.infrastructure.repository import SalesRepository
from bond_profit.ui.error_hook import install_excepthook
from bond_profit.ui.main_window import MainWindow

logger = logging.getLogger(__name__)

_SINGLE_INSTANCE_KEY = "BondProfit-SingleInstance"


def main() -> int:
    setup_logging()
    install_excepthook()  # 阶段 5：未捕获异常写日志 + 中文提示，不强制退出
    logger.info("应用启动，版本 %s", bond_profit.__version__)

    app = QApplication(sys.argv)
    app.setApplicationName("可转债收益记录")
    app.setOrganizationName("BondProfit")

    if _is_another_instance_running():
        logger.info("检测到已有实例运行，通知其激活窗口后退出")
        _notify_existing_instance()
        return 0

    data_root = default_database_path().parent.parent
    auto_dir, protected_dir = backup_dirs(data_root)
    db_path = default_database_path()

    # ---- 启动预检（§5.3 / §6.5）：只读识别，不做任何写入 -----------------------
    try:
        db_version = inspect_database(db_path)
    except DatabaseCorruptError as exc:
        logger.critical("数据库损坏，停止启动：%s", exc.path, exc_info=True)
        QMessageBox.critical(None, "数据库损坏", str(exc))
        return 1

    if db_version > SCHEMA_VERSION:
        # MIG-03：旧程序拒绝写入新版数据库，提示升级
        logger.error("数据库版本 %s 高于程序版本 %s", db_version, SCHEMA_VERSION)
        QMessageBox.critical(
            None,
            "需要升级程序",
            f"当前数据库版本（{db_version}）比程序支持的版本（{SCHEMA_VERSION}）"
            "更新，旧程序已停止启动以保护数据。请使用新版程序打开。",
        )
        return 1

    if 0 < db_version < SCHEMA_VERSION:
        # §5.3：迁移前先创建并验证升级前保护备份；失败停止启动，原数据不动
        try:
            pre_conn = sqlite3.connect(db_path)
            try:
                create_backup(pre_conn, protected_dir, "protected")
            finally:
                pre_conn.close()
        except BackupError:
            logger.error("升级前保护备份失败，停止迁移", exc_info=True)
            QMessageBox.critical(
                None,
                "升级前备份失败",
                "创建升级前保护备份失败，已停止启动。原数据未改动，"
                "请检查磁盘空间后重试。",
            )
            return 1

    # ---- 打开数据库（版本过旧时在 connect 内执行迁移） ------------------------
    try:
        conn = connect()
    except DatabaseCorruptError as exc:
        # §6.5：停止正常使用，保留损坏文件，引导手动恢复；不得静默建空库
        logger.critical("数据库损坏，停止启动：%s", exc.path, exc_info=True)
        QMessageBox.critical(None, "数据库损坏", str(exc))
        return 1
    except DatabaseTooNewError as exc:
        logger.error("数据库版本过新：%s", exc.path, exc_info=True)
        QMessageBox.critical(None, "需要升级程序", str(exc))
        return 1
    except MigrationError as exc:
        # MIG-02：迁移失败停止启动，原数据保留
        logger.critical("数据库迁移失败，停止启动", exc_info=True)
        QMessageBox.critical(None, "数据库迁移失败", str(exc))
        return 1

    backup_service = BackupService(
        conn, StateStore(data_root / "state.json"), auto_dir, protected_dir
    )
    service = SalesService(SalesRepository(conn), on_change=backup_service.mark_dirty)
    excel_service = ExcelService(service)

    try:
        backup_service.run_auto_backup()  # §6.1 启动时检查
    except BackupError:
        # BAK-03：醒目但不阻断，允许重试；批次 16 接入备份页重试入口
        logger.warning("启动自动备份失败，可在备份页重试", exc_info=True)

    window = MainWindow(service, excel_service, backup_service=backup_service)
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
