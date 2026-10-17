"""备份服务层（文档 §6.1）：自动备份策略、手动备份、脏标记。

策略（§6.1 / BAK-01～03）：
- 本机日历日每天最多一份自动备份：当天已成功则跳过；
- 只在数据自上次成功备份后有变更（脏标记）时备份；
- 失败不计当天成功次数、状态不变，调用方可直接重试；不阻断正常录入。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from bond_profit.infrastructure.backup import BackupInfo, create_backup
from bond_profit.infrastructure.backup_state import StateStore

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(
        self,
        conn,
        state_store: StateStore,
        auto_dir: Path | str,
        protected_dir: Path | str,
    ) -> None:
        self._conn = conn
        self._state_store = state_store
        self._auto_dir = Path(auto_dir)
        self._protected_dir = Path(protected_dir)

    # ---- 脏标记 -------------------------------------------------------------

    def mark_dirty(self) -> None:
        """数据发生变更后调用；立即持久化，重启后仍生效。"""
        state = self._state_store.load()
        if not state.dirty:
            state.dirty = True
            self._state_store.save(state)

    # ---- 自动备份（§6.1） ----------------------------------------------------

    def run_auto_backup(self, now: datetime | None = None) -> BackupInfo | None:
        """启动时与运行期定期调用；返回 None 表示本次无需备份。

        抛出 BackupError 表示本次备份失败：状态不变（不计当天成功次数），
        可再次调用重试，不影响正常录入（BAK-03）。
        """
        today = (now or datetime.now()).strftime("%Y-%m-%d")
        state = self._state_store.load()
        if state.last_auto_backup_date == today:
            return None  # 当天已成功一份自动备份（BAK-01）
        if not state.dirty:
            return None  # 自上次成功备份后无变更（§6.1）

        info = create_backup(self._conn, self._auto_dir, "auto")
        state.last_auto_backup_date = today
        state.dirty = False
        self._state_store.save(state)
        return info

    # ---- 手动备份（§6.2） ----------------------------------------------------

    def run_manual_backup(self, dest_dir: Path | str) -> BackupInfo:
        """用户自选路径手动备份；成功后清除脏标记（数据已有有效快照）。"""
        info = create_backup(self._conn, dest_dir, "manual")
        state = self._state_store.load()
        if state.dirty:
            state.dirty = False
            self._state_store.save(state)
        return info
