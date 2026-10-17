"""全局未捕获异常兜底（阶段 5 UI 稳定性，已批准默认决策②）。

- 未捕获异常写入日志（完整堆栈）；
- 弹一次中文提示（含日志指引），不自动退出；
- 数据层受控异常仍由各服务/UI 捕获处理，不经过本钩子。
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from types import TracebackType

logger = logging.getLogger(__name__)

Notify = Callable[[str], None]


def format_crash_message(exc_value: BaseException) -> str:
    """面向用户的崩溃提示文案。"""
    return (
        f"程序遇到未预期的错误：{exc_value}\n\n"
        "错误详情已记录到日志，程序将继续运行。\n"
        "如反复出现，请通过主窗口「打开日志」按钮找到日志文件夹反馈。"
    )


def make_crash_hook(notify: Notify) -> Callable[[type, BaseException, TracebackType | None], None]:
    """构造 sys.excepthook 兼容的钩子函数；notify 由调用方注入（测试友好）。"""

    def hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        logger.critical("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        try:
            notify(format_crash_message(exc_value))
        except Exception:
            # 提示失败不影响兜底本身：日志已记录
            logger.warning("异常提示展示失败", exc_info=True)

    return hook


def _default_notify(message: str) -> None:
    """默认提示：Qt 事件循环存在时弹窗，否则只留日志。"""
    from PySide6.QtWidgets import QApplication, QMessageBox

    if QApplication.instance() is None:
        return
    QMessageBox.warning(None, "程序遇到未预期的错误", message)


def install_excepthook(notify: Notify | None = None) -> None:
    """安装全局兜底钩子；须在 setup_logging 之后调用以保证日志落盘。"""
    sys.excepthook = make_crash_hook(notify or _default_notify)
