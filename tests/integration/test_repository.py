"""数据库层集成测试。全部使用临时路径（文档 8.4 红线）。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal

import pytest

from bond_profit.infrastructure.database import SCHEMA_VERSION, connect, default_database_path
from bond_profit.infrastructure.repository import RepositoryError, SalesRepository


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "data" / "app.db"


@pytest.fixture()
def repo(db_path):
    conn = connect(db_path)
    yield SalesRepository(conn)
    conn.close()


def make_record(**overrides):
    from bond_profit.domain.models import SaleRecord

    defaults = dict(
        bond_name="平银转债",
        bond_code="012345",
        sale_date=date(2026, 1, 15),
        sale_price=Decimal("130.00"),
        quantity=10,
        note="测试",
    )
    defaults.update(overrides)
    return SaleRecord(**defaults)


# ---- database.connect ------------------------------------------------------


def test_connect_creates_schema_and_version(db_path):
    conn = connect(db_path)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert version == SCHEMA_VERSION
    assert "sales" in tables
    conn.close()


def test_default_path_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    expected = tmp_path / "ConvertibleBondProfit" / "data" / "app.db"
    assert default_database_path() == expected


# ---- 增查（含 REC-01 重复录入） --------------------------------------------


def test_add_returns_id_and_timestamps(repo):
    added = repo.add(make_record())
    assert added.id is not None
    assert isinstance(added.created_at, datetime)
    fetched = repo.get_by_id(added.id)
    assert fetched == added


def test_rec01_manual_duplicate_records_allowed(repo):
    """两条完全相同的记录均可保存，内部 id 不同。"""
    first = repo.add(make_record())
    second = repo.add(make_record())
    assert first.id != second.id
    assert repo.count() == 2


def test_decimal_and_date_roundtrip(repo):
    added = repo.add(
        make_record(sale_price=Decimal("98.50"), sale_date=date(2025, 12, 31))
    )
    fetched = repo.get_by_id(added.id)
    assert fetched.sale_price == Decimal("98.50")
    assert fetched.sale_date == date(2025, 12, 31)


# ---- 改删 ------------------------------------------------------------------


def test_update_changes_record(repo):
    added = repo.add(make_record())
    added.sale_price = Decimal("110.00")
    added.note = "改过"
    updated = repo.update(added)

    assert updated.sale_price == Decimal("110.00")
    assert updated.updated_at >= updated.created_at
    assert repo.get_by_id(added.id).note == "改过"


def test_update_missing_record_raises(repo):
    record = make_record(id=9999)
    with pytest.raises(RepositoryError):
        repo.update(record)


def test_delete_removes_record(repo):
    added = repo.add(make_record())
    repo.delete(added.id)
    assert repo.get_by_id(added.id) is None
    assert repo.count() == 0


def test_delete_missing_record_raises(repo):
    with pytest.raises(RepositoryError):
        repo.delete(9999)


# ---- 排序（§3.3 默认次序） --------------------------------------------------


def test_list_all_orders_date_desc_then_id_desc(repo):
    older = repo.add(make_record(sale_date=date(2025, 1, 1)))
    newer_later = repo.add(make_record(sale_date=date(2026, 5, 1)))
    same_a = repo.add(make_record(sale_date=date(2026, 1, 15), note="a"))
    same_b = repo.add(make_record(sale_date=date(2026, 1, 15), note="b"))

    ids = [r.id for r in repo.list_all()]
    assert ids == [newer_later.id, same_b.id, same_a.id, older.id]


# ---- 写入失败不假装成功（§5.2 / REC-05 数据层） -----------------------------


def test_write_failure_raises_and_writes_nothing(db_path):
    """用 SQLite authorizer 拒绝 INSERT，模拟真实写入失败（§5.2 / REC-05）。"""
    conn = connect(db_path)
    repo = SalesRepository(conn)

    def deny_insert(action, *_args):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_INSERT else sqlite3.SQLITE_OK

    conn.set_authorizer(deny_insert)
    with pytest.raises(RepositoryError):
        repo.add(make_record())
    assert repo.count() == 0
    conn.close()


# ---- 数据库约束兜底（§5.1 约束互补） ----------------------------------------


def test_db_constraints_reject_bad_data(db_path):
    conn = connect(db_path)
    bad_rows = [
        # 代码不是六位数字
        ("平银转债", "1234", "2026-01-15", 13000, 10, "", "t", "t"),
        # 日期格式非法
        ("平银转债", "012345", "2026-1-5", 13000, 10, "", "t", "t"),
        # 价格为 0
        ("平银转债", "012345", "2026-01-15", 0, 10, "", "t", "t"),
        # 数量为 0
        ("平银转债", "012345", "2026-01-15", 13000, 0, "", "t", "t"),
    ]
    for row in bad_rows:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sales (bond_name, bond_code, sale_date, "
                "sale_price_cents, quantity, note, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
    conn.close()
