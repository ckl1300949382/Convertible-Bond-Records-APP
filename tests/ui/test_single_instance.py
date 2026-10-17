"""单实例控制测试（§3.6 逻辑层）。"""

from __future__ import annotations

import uuid

import pytest

from bond_profit.app import (
    _is_another_instance_running,
    _notify_existing_instance,
    _start_single_instance_server,
)

pytest.importorskip("PySide6.QtNetwork")


@pytest.fixture()
def key(qapp):
    return f"BondProfit-Test-{uuid.uuid4().hex}"


def test_no_instance_running_initially(key):
    assert not _is_another_instance_running(key)


def test_instance_detected_when_server_listens(key, qapp):
    from PySide6.QtWidgets import QMainWindow

    window = QMainWindow()
    server = _start_single_instance_server(window, key=key)
    try:
        assert _is_another_instance_running(key)
    finally:
        server.close()


def test_notify_existing_instance_does_not_crash(key, qapp):
    from PySide6.QtWidgets import QMainWindow

    window = QMainWindow()
    server = _start_single_instance_server(window, key=key)
    try:
        _notify_existing_instance(key)  # 不抛异常即可（连接并写入 activate）
    finally:
        server.close()
