"""备份核心层（文档 §6.1–§6.3）。

原则：
- 快照使用 SQLite 官方备份 API（conn.backup），保证一致性，不直接复制运行中的库文件；
- 先写临时文件，校验（integrity_check + 记录数）通过后同目录原子发布；
- manifest JSON 仅作元数据辅助，读取备份列表一律以实际文件检查为准（§6.3）；
- 保留策略只作用于 auto 目录：新备份成功落盘后才清理最旧的，
  备份失败不得删除任何旧备份（§6.2）。
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

AUTO_BACKUP_KEEP = 30  # 自动备份保留份数（§6.2）
_KINDS = ("auto", "manual", "protected")  # 自动 / 手动 / 升级前与恢复前保护
_NAME_PATTERN = "app_*.db"


class BackupError(Exception):
    """备份操作失败。message 面向用户（中文），技术细节通过日志记录。"""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    kind: str
    created_at: str
    record_count: int
    schema_version: int
    verified: bool


def manifest_path(backup_path: Path) -> Path:
    return backup_path.with_name(backup_path.stem + ".manifest.json")


def _snapshot(source: sqlite3.Connection, dest: sqlite3.Connection) -> None:
    """SQLite 官方在线备份 API；独立函数便于测试注入故障（BAK-05）。"""
    source.backup(dest)


def _validate_backup_file(path: Path) -> tuple[int, int]:
    """校验备份文件：完整性 + sales 表可读。返回 (记录数, 库版本)。"""
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError("备份文件完整性校验未通过")
        record_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
        return record_count, schema_version
    finally:
        conn.close()


def create_backup(
    conn: sqlite3.Connection,
    dest_dir: Path | str,
    kind: str,
    *,
    keep: int = AUTO_BACKUP_KEEP,
) -> BackupInfo:
    """创建备份并安全发布到 dest_dir；kind 决定是否触发保留清理。

    任何一步失败都不会改动目录里已有的旧备份（§6.2）。
    """
    if kind not in _KINDS:
        raise BackupError(f"未知的备份类型：{kind}")
    conn.commit()  # 确保快照包含已写入但未提交的数据

    dest_dir = Path(dest_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("备份目录创建失败：%s", dest_dir)
        raise BackupError("备份目录创建失败，请检查磁盘空间与写入权限") from exc

    now = datetime.now()
    final_path = dest_dir / f"app_{now.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}.db"
    temp_path = dest_dir / f".tmp_{final_path.name}"

    try:
        dest = sqlite3.connect(temp_path)
        try:
            _snapshot(conn, dest)
        finally:
            dest.close()
        record_count, schema_version = _validate_backup_file(temp_path)
        os.replace(temp_path, final_path)  # 同目录原子发布
    except BackupError:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        logger.exception("备份创建失败：%s", dest_dir)
        raise BackupError("备份创建失败，请检查磁盘空间与写入权限") from exc

    info = BackupInfo(
        path=final_path,
        kind=kind,
        created_at=now.isoformat(timespec="seconds"),
        record_count=record_count,
        schema_version=schema_version,
        verified=True,
    )
    _write_manifest(info)

    if kind == "auto":
        try:
            prune_auto_backups(dest_dir, keep=keep)
        except OSError:
            # 清理失败不影响本次已成功发布的备份（宁可多留不可误删，§6.2）
            logger.warning("自动备份清理失败，本次跳过", exc_info=True)
    return info


def _write_manifest(info: BackupInfo) -> None:
    """写入配套 manifest；失败仅告警——备份有效性以库文件本身为准（§6.3）。"""
    payload = {
        "file": info.path.name,
        "kind": info.kind,
        "created_at": info.created_at,
        "record_count": info.record_count,
        "schema_version": info.schema_version,
        "verified": True,
    }
    try:
        manifest_path(info.path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        logger.warning("manifest 写入失败：%s", info.path, exc_info=True)


def _read_manifest(backup_path: Path) -> dict:
    try:
        text = manifest_path(backup_path).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError):
        return {}


def read_backup_info(path: Path | str) -> BackupInfo:
    """检查单个备份文件（§6.3：以实际文件检查为准，不只相信 manifest）。

    损坏文件不抛异常，返回 verified=False，供列表展示与恢复流程拒绝。
    """
    path = Path(path)
    if not path.is_file():
        raise BackupError("备份文件不存在")

    record_count, schema_version, verified = 0, 0, False
    try:
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if result == "ok":
                record_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
                schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
                verified = True
        finally:
            conn.close()
    except sqlite3.Error:
        verified = False

    meta = _read_manifest(path)
    created_at = meta.get("created_at") or datetime.fromtimestamp(
        path.stat().st_mtime
    ).isoformat(timespec="seconds")
    kind = meta.get("kind")
    if kind not in _KINDS:
        kind = path.parent.name if path.parent.name in _KINDS else "unknown"
    return BackupInfo(path, kind, created_at, record_count, schema_version, verified)


def list_backups(*dirs: Path | str) -> list[BackupInfo]:
    """列出各目录中的备份（最新在前）。目录不存在视为空。"""
    infos: list[BackupInfo] = []
    for root in dirs:
        root = Path(root)
        if not root.is_dir():
            continue
        for file in root.glob(_NAME_PATTERN):
            try:
                infos.append(read_backup_info(file))
            except (BackupError, OSError):
                logger.warning("跳过无法读取的备份文件：%s", file, exc_info=True)
    infos.sort(key=lambda info: info.created_at, reverse=True)
    return infos


def prune_auto_backups(auto_dir: Path | str, *, keep: int = AUTO_BACKUP_KEEP) -> list[Path]:
    """清理最旧的自动备份，返回被删除的文件。

    只处理符合备份命名规则的文件；删除前不校验新旧备份状态——
    调用方必须在"新备份成功发布之后"才调用本函数（§6.2）。
    """
    auto_dir = Path(auto_dir)
    backups = sorted(
        auto_dir.glob(_NAME_PATTERN),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    removed: list[Path] = []
    for old in backups[max(keep, 0):]:
        old.unlink(missing_ok=True)
        manifest_path(old).unlink(missing_ok=True)
        removed.append(old)
    return removed


def backup_dirs(data_dir: Path | str) -> tuple[Path, Path]:
    """标准备份目录布局（§5.1）：backups/auto 与 backups/protected。"""
    data_dir = Path(data_dir)
    return data_dir / "backups" / "auto", data_dir / "backups" / "protected"
