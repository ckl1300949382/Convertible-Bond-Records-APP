"""备份策略状态持久化（阶段 4）：state.json 记录最近成功自动备份日期与脏标记。

文件缺失或损坏时按安全默认处理（视为有变更、从未自动备份）——
宁可多备份一次，不漏备（§6.1）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BackupState:
    last_auto_backup_date: str = ""  # "YYYY-MM-DD"；空表示从未成功自动备份
    dirty: bool = True  # 自上次成功备份后数据是否有变更


class StateStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def load(self) -> BackupState:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            return BackupState(
                last_auto_backup_date=str(payload.get("last_auto_backup_date", "")),
                dirty=bool(payload.get("dirty", True)),
            )
        except (OSError, json.JSONDecodeError, AttributeError, TypeError):
            logger.warning("状态文件缺失或损坏，按安全默认处理：%s", self._path)
            return BackupState()

    def save(self, state: BackupState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_auto_backup_date": state.last_auto_backup_date,
            "dirty": state.dirty,
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
