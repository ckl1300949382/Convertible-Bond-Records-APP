"""阶段 0 冒烟测试：包导入、版本号、日志初始化（全部使用临时目录）。"""

from __future__ import annotations

import logging

import bond_profit
from bond_profit.infrastructure.logging import setup_logging


def test_package_importable_and_version():
    assert bond_profit.__version__ == "0.1.0"


def test_setup_logging_creates_file_and_writes(tmp_path):
    log_dir = tmp_path / "logs"
    log_file = setup_logging(log_dir=log_dir)

    assert log_file == log_dir / "app.log"
    logging.getLogger("test_smoke").info("写入一条测试日志")
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")
    assert "写入一条测试日志" in content
    assert "INFO" in content


def test_setup_logging_does_not_duplicate_handlers(tmp_path):
    setup_logging(log_dir=tmp_path)
    setup_logging(log_dir=tmp_path)

    file_handlers = [
        h
        for h in logging.getLogger().handlers
        if type(h).__name__ == "RotatingFileHandler"
    ]
    assert len(file_handlers) == 1
