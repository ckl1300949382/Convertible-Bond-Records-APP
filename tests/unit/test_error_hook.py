"""全局异常兜底测试（阶段 5 UI 稳定性）。"""

from __future__ import annotations

import logging
import sys

from bond_profit.ui.error_hook import format_crash_message, install_excepthook, make_crash_hook


def test_crash_message_is_chinese_and_actionable():
    message = format_crash_message(ValueError("boom"))
    assert "boom" in message
    assert "未预期的错误" in message
    assert "打开日志" in message  # 指引用户找日志反馈


def test_hook_logs_critical_and_notifies(caplog):
    captured = []
    hook = make_crash_hook(captured.append)
    with caplog.at_level(logging.CRITICAL):
        hook(ValueError, ValueError("boom"), None)

    assert len(captured) == 1
    assert "boom" in captured[0]
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)


def test_hook_does_not_propagate_notify_failure(caplog):
    def broken_notify(message):
        raise RuntimeError("模拟弹窗失败")

    hook = make_crash_hook(broken_notify)
    with caplog.at_level(logging.WARNING):
        hook(ValueError, ValueError("boom"), None)  # 不应向外抛异常

    assert any("异常提示展示失败" in r.getMessage() for r in caplog.records)


def test_install_excepthook_replaces_and_can_restore():
    original = sys.excepthook
    try:
        captured = []
        install_excepthook(captured.append)
        assert sys.excepthook is not original

        sys.excepthook(ValueError, ValueError("installed"), None)
        assert len(captured) == 1
    finally:
        sys.excepthook = original  # 不影响其他测试
