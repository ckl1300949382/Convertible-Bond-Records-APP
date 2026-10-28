"""备份核心层测试（§6.1–§6.3 / BAK-04、05、06）。全部使用临时目录，不碰真实数据。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta

import pytest

from bond_profit.infrastructure import backup as backup_module
from bond_profit.infrastructure.backup import (
    BackupError,
    create_backup,
    list_backups,
    manifest_path,
    prune_auto_backups,
    read_backup_info,
)
from bond_profit.infrastructure.database import connect

_NAME_RE = re.compile(r"^app_\d{8}_\d{6}_[0-9a-f]{6}\.db$")


@pytest.fixture()
def conn(tmp_path):
    conn = connect(tmp_path / "app.db")
    now = "2026-10-17T10:00:00"
    conn.executemany(
        "INSERT INTO sales (bond_name, bond_code, sale_date, sale_price_cents, "
        "quantity, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("平银转债", "012345", "2026-01-15", 13000, 10, "", now, now),
            ("中信转债", "123456", "2026-02-01", 9500, 20, "亏损", now, now),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


# ---- 创建与发布（§6.3） ------------------------------------------------------

def test_backup_creates_verified_snapshot(conn, tmp_path):
    dest = tmp_path / "backups" / "auto"
    info = create_backup(conn, dest, "auto")

    assert _NAME_RE.match(info.path.name)  # 文件名含时间与唯一后缀
    assert info.verified and info.record_count == 2 and info.schema_version == 1
    assert manifest_path(info.path).is_file()

    # 快照内容与源库一致
    check = sqlite3.connect(info.path)
    try:
        rows = check.execute(
            "SELECT bond_name, bond_code FROM sales ORDER BY id"
        ).fetchall()
    finally:
        check.close()
    assert rows == [("平银转债", "012345"), ("中信转债", "123456")]


def test_backup_names_unique_within_same_second(conn, tmp_path):
    dest = tmp_path / "backups" / "auto"
    first = create_backup(conn, dest, "auto")
    second = create_backup(conn, dest, "auto")
    assert first.path != second.path


def test_manifest_metadata(conn, tmp_path):
    dest = tmp_path / "manual_backups"
    info = create_backup(conn, dest, "manual")
    payload = json.loads(manifest_path(info.path).read_text(encoding="utf-8"))
    assert payload["file"] == info.path.name
    assert payload["kind"] == "manual"
    assert payload["record_count"] == 2
    assert payload["schema_version"] == 1
    assert payload["verified"] is True


def test_create_backup_rejects_unknown_kind(conn, tmp_path):
    with pytest.raises(BackupError):
        create_backup(conn, tmp_path, "wrong")


# ---- 列表以实际文件为准（§6.3） ----------------------------------------------

def test_list_reads_actual_file_over_manifest(conn, tmp_path):
    dest = tmp_path / "backups" / "auto"
    info = create_backup(conn, dest, "auto")
    manifest = json.loads(manifest_path(info.path).read_text(encoding="utf-8"))
    manifest["record_count"] = 99
    manifest_path(info.path).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    listed = list_backups(dest)
    assert len(listed) == 1
    assert listed[0].record_count == 2  # 实际文件检查结果，非 manifest
    assert listed[0].verified is True


def test_corrupt_file_reported_unverified(conn, tmp_path):
    dest = tmp_path / "backups" / "auto"
    create_backup(conn, dest, "auto")
    (dest / "app_20990101_000000_deadbe.db").write_bytes(b"not a database")

    listed = list_backups(dest)
    assert len(listed) == 2
    corrupt = next(b for b in listed if not b.verified)
    assert corrupt.record_count == 0
    assert corrupt.schema_version == 0


def test_list_empty_and_missing_dirs(tmp_path):
    assert list_backups(tmp_path / "backups" / "auto") == []
    assert list_backups(tmp_path / "no_such_dir") == []


def test_list_sorted_newest_first(conn, tmp_path):
    dest = tmp_path / "backups" / "auto"
    first = create_backup(conn, dest, "auto")
    second = create_backup(conn, dest, "auto")
    # 同秒创建时 created_at 相同、次序不稳定；把第二份 manifest 时间对准第一份 +1 秒。
    # 注意：不要写死绝对时间，否则等到那天变成「过去」，排序断言就会反掉。
    later = datetime.fromisoformat(first.created_at) + timedelta(seconds=1)
    manifest = json.loads(manifest_path(second.path).read_text(encoding="utf-8"))
    manifest["created_at"] = later.isoformat(timespec="seconds")
    manifest_path(second.path).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    listed = list_backups(dest)
    assert [b.path for b in listed] == [second.path, first.path]


# ---- 保留策略（§6.2 / BAK-04、05、06） ----------------------------------------

def test_prune_removes_only_oldest(tmp_path):
    """BAK-04：第 31 份成功后只清理最旧一份。用显式 mtime 保证确定性。"""
    auto = tmp_path / "backups" / "auto"
    auto.mkdir(parents=True)
    names = []
    for index in range(3):
        path = auto / f"app_20261017_0000{index}_00000{index}.db"
        path.write_bytes(b"x")
        names.append(path)
    base = time.mktime((2026, 10, 17, 10, 0, 0, 0, 0, -1))
    for index, path in enumerate(names):
        stamp = base + index * 60
        os.utime(path, (stamp, stamp))

    removed = prune_auto_backups(auto, keep=2)

    assert [p.name for p in removed] == [names[0].name]  # 只删最旧一份
    assert not manifest_path(names[0]).exists()  # 配套 manifest 一并清理
    assert names[1].exists() and names[2].exists()


def test_auto_backup_keeps_30_after_31st(conn, tmp_path):
    """BAK-04 集成：第 31 份自动备份成功后保留 30 份且最新一份存活。"""
    dest = tmp_path / "backups" / "auto"
    created = [create_backup(conn, dest, "auto").path.name for _ in range(31)]

    remaining = {p.name for p in dest.glob("app_*.db")}
    assert len(remaining) == 30
    assert created[-1] in remaining  # 最新一份不被清理
    assert not (dest / (".tmp_" + created[-1])).exists()  # 无临时文件残留


def test_failed_backup_keeps_old_backups(conn, tmp_path, monkeypatch):
    """BAK-05：新备份创建失败时旧备份不被删除，且无临时文件残留。"""
    dest = tmp_path / "backups" / "auto"
    create_backup(conn, dest, "auto")
    create_backup(conn, dest, "auto")
    before = sorted(p.name for p in dest.iterdir())

    def broken_snapshot(source, dest_conn):
        raise RuntimeError("模拟复制失败")

    monkeypatch.setattr(backup_module, "_snapshot", broken_snapshot)
    with pytest.raises(BackupError):
        create_backup(conn, dest, "auto")

    assert sorted(p.name for p in dest.iterdir()) == before
    assert not list(dest.glob(".tmp_*"))


def test_protected_and_manual_never_pruned(conn, tmp_path):
    """BAK-06：保护备份与手动备份不参与自动清理。"""
    for kind in ("protected", "manual"):
        dest = tmp_path / kind
        for _ in range(35):
            create_backup(conn, dest, kind)
        assert len(list(dest.glob("app_*.db"))) == 35


def test_unrelated_files_untouched_by_prune(conn, tmp_path):
    dest = tmp_path / "backups" / "auto"
    dest.mkdir(parents=True)
    (dest / "notes.txt").write_text("随手记", encoding="utf-8")
    (dest / "other.db").write_bytes(b"x")  # 不符合备份命名规则
    for _ in range(31):
        create_backup(conn, dest, "auto")

    assert (dest / "notes.txt").exists()
    assert (dest / "other.db").exists()
