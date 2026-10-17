"""备份服务层（文档 §6.1、§6.4）：自动备份策略、手动备份、恢复、脏标记。

策略（§6.1 / BAK-01～03）：
- 本机日历日每天最多一份自动备份：当天已成功则跳过；
- 只在数据自上次成功备份后有变更（脏标记）时备份；
- 失败不计当天成功次数、状态不变，调用方可直接重试；不阻断正常录入。

恢复（§6.4 / RES-01～03）：
- 校验备份→恢复前保护备份→临时位置恢复→按需迁移→
  完整性/记录数/收益汇总比对→官方备份 API 写回活动连接；
- 任一步失败都不覆盖当前有效数据库。
"""

from __future__ import annotations

import logging
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bond_profit.infrastructure import database
from bond_profit.infrastructure.backup import (
    BackupInfo,
    create_backup,
    list_backups,
    read_backup_info,
)
from bond_profit.infrastructure.backup_state import StateStore

logger = logging.getLogger(__name__)


class RestoreError(Exception):
    """恢复被拒绝或失败。message 面向用户（中文）；当前数据未被改动。"""


@dataclass(frozen=True)
class _Fingerprint:
    schema_version: int
    record_count: int
    total_profit_cents: int


@dataclass(frozen=True)
class RestoreReport:
    backup: BackupInfo  # 恢复来源
    protected: BackupInfo  # 恢复前保护备份
    record_count: int
    total_profit_cents: int


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

    # ---- 备份列表 ------------------------------------------------------------

    def list_backups(self) -> list[BackupInfo]:
        """列出自动与保护备份（最新在前）。

        手动备份在用户自选目录，不纳入本列表（已批准默认决策②）。
        """
        return list_backups(self._auto_dir, self._protected_dir)

    # ---- 手动恢复（§6.4） ----------------------------------------------------

    def restore_from_backup(self, backup_path: Path | str) -> RestoreReport:
        """从备份恢复。任一步失败都不覆盖当前有效数据库（§6.4）。

        用户确认对话框由 UI 层负责；本方法从校验开始执行。
        """
        source_path = Path(backup_path)

        # 1. 校验文件与版本（以实际文件检查为准，§6.3/§6.4）
        info = read_backup_info(source_path)
        if not info.verified:
            raise RestoreError("备份文件已损坏或无法读取，已拒绝恢复；当前数据未改动")
        if info.schema_version > database.SCHEMA_VERSION:
            raise RestoreError(
                f"该备份的数据库版本（{info.schema_version}）比当前程序支持的版本"
                f"（{database.SCHEMA_VERSION}）更新，请先升级程序再恢复"
            )

        # 2. 先创建并验证当前数据库的保护备份（§6.4）
        protected = create_backup(self._conn, self._protected_dir, "protected")

        # 3. 独立临时位置恢复 → 按需迁移 → 校验 → 写回活动连接
        try:
            with tempfile.TemporaryDirectory(prefix="bondprofit_restore_") as tmp:
                temp_db = Path(tmp) / "restored.db"
                _restore_to_temp(source_path, temp_db)
                fingerprint = self._validate_temp(temp_db, info)
                if fingerprint.schema_version < database.SCHEMA_VERSION:
                    temp_conn = sqlite3.connect(temp_db)
                    try:
                        database.run_migrations(temp_conn, fingerprint.schema_version)
                    finally:
                        temp_conn.close()
                    fingerprint = self._validate_temp(temp_db, info)  # 迁移后复验

                self._conn.commit()  # 确保无悬挂事务
                temp_src = sqlite3.connect(f"{temp_db.as_uri()}?mode=ro", uri=True)
                try:
                    # 官方备份 API 写回活动连接：整库替换在 SQLite 事务内完成，
                    # 中途出错目标库自动回滚到恢复前状态（RES-03）
                    temp_src.backup(self._conn)
                finally:
                    temp_src.close()
        except Exception as exc:
            logger.error("恢复失败，当前数据未改动", exc_info=True)
            raise RestoreError(
                "恢复失败，当前数据未改动；恢复前的保护备份已保留，可重试"
            ) from exc

        # 已批准默认决策①：恢复后置脏并记录当日已备份 → 次日首次检查生成新自动备份
        state = self._state_store.load()
        state.dirty = True
        state.last_auto_backup_date = datetime.now().strftime("%Y-%m-%d")
        self._state_store.save(state)

        return RestoreReport(
            backup=info,
            protected=protected,
            record_count=fingerprint.record_count,
            total_profit_cents=fingerprint.total_profit_cents,
        )

    def _validate_temp(self, temp_db: Path, expected: BackupInfo) -> _Fingerprint:
        """校验临时恢复库：完整性、记录数、收益汇总与备份文件一致（§6.4）。"""
        restored = read_backup_info(temp_db)
        if not restored.verified:
            raise RestoreError("恢复的临时文件未通过完整性校验，已中止")
        count, profit_cents = _database_fingerprint(temp_db)
        if count != expected.record_count:
            raise RestoreError("恢复数据的记录数与备份文件不一致，已中止")
        source_count, source_profit = _database_fingerprint(expected.path)
        if profit_cents != source_profit:
            raise RestoreError("恢复数据的收益汇总与备份文件不一致，已中止")
        return _Fingerprint(restored.schema_version, count, profit_cents)


def _restore_to_temp(source_path: Path, temp_db: Path) -> None:
    """把备份文件复制到独立临时位置（官方备份 API）。独立函数便于测试注入故障。"""
    source = sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(temp_db)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


def _database_fingerprint(path: Path) -> tuple[int, int]:
    """以实际文件检查为准：返回 (记录数, 收益总分)。

    收益口径与仓储排序一致：(单价分 − 10000) × 数量，成本固定 100 元/张。
    """
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        record_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        total = conn.execute(
            "SELECT COALESCE(SUM((sale_price_cents - 10000) * quantity), 0) FROM sales"
        ).fetchone()[0]
        return record_count, int(total)
    finally:
        conn.close()
