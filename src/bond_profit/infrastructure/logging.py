"""应用日志初始化。

默认写入 %LOCALAPPDATA%/ConvertibleBondProfit/logs/app.log，
滚动保留 5 份历史，每份上限 1MB。
测试通过 log_dir 参数注入临时目录（文档 8.4：测试不碰真实用户数据）。
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FILE_NAME = "app.log"
_MAX_BYTES = 1 * 1024 * 1024
_BACKUP_COUNT = 5
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def default_log_dir() -> Path:
    """真实运行时的日志目录：%LOCALAPPDATA%/ConvertibleBondProfit/logs。"""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise RuntimeError("未找到 LOCALAPPDATA 环境变量，无法确定日志目录")
    return Path(base) / "ConvertibleBondProfit" / "logs"


def setup_logging(log_dir: Path | None = None) -> Path:
    """初始化根日志器，返回日志文件路径。

    log_dir 为 None 时使用默认真实目录。
    重复调用时移除旧的文件 Handler，避免日志重复写入。
    """
    directory = Path(log_dir) if log_dir is not None else default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / _LOG_FILE_NAME

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in list(root.handlers):
        if isinstance(handler, RotatingFileHandler):
            root.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    return log_file
