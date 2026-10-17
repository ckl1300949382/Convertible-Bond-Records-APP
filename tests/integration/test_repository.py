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


# ---- 分页查询（§3.3 搜索/筛选/排序，UI-01 数据层） --------------------------

from bond_profit.domain.models import RecordQuery  # noqa: E402


def seed_page_records(repo) -> None:
    """25 条记录：跨 2025/2026 两年，价格与数量各不相同。"""
    for i in range(20):
        repo.add(
            make_record(
                bond_name=f"转债{i:02d}号",
                bond_code=f"1234{i:02d}",
                sale_date=date(2026, 1, i % 12 + 1),
                sale_price=Decimal(f"10{i}.00"),
                quantity=i + 1,
            )
        )
    repo.add(make_record(bond_name="平银转债", bond_code="000000", sale_date=date(2025, 12, 31)))
    repo.add(make_record(bond_name="中信转债", bond_code="111111", sale_date=date(2025, 6, 1)))
    repo.add(make_record(bond_name="浦发转债", bond_code="222222", sale_date=date(2026, 3, 1)))
    repo.add(make_record(bond_name="光大同号", bond_code="333333", sale_date=date(2026, 3, 15)))
    repo.add(make_record(bond_name="苏行转债", bond_code="444444", sale_date=date(2026, 7, 1)))


def test_list_page_limit_and_offset(repo):
    seed_page_records(repo)
    query = RecordQuery()
    first = repo.list_page(query, offset=0, limit=20)
    second = repo.list_page(query, offset=20, limit=20)
    assert len(first) == 20
    assert len(second) == 5
    assert {r.id for r in first}.isdisjoint({r.id for r in second})


def test_list_page_default_order_matches_list_all(repo):
    seed_page_records(repo)
    query = RecordQuery()
    paged_ids = [r.id for r in repo.list_page(query, 0, 100)]
    assert paged_ids == [r.id for r in repo.list_all()]


def test_count_filtered_no_filter(repo):
    seed_page_records(repo)
    assert repo.count_filtered(RecordQuery()) == 25


def test_keyword_matches_name_or_code(repo):
    seed_page_records(repo)
    assert repo.count_filtered(RecordQuery(keyword="平银")) == 1
    assert repo.count_filtered(RecordQuery(keyword="111111")) == 1
    # 20 条「转债XX号」+ 平银转债/中信转债/浦发转债/苏行转债；光大同号不含
    assert repo.count_filtered(RecordQuery(keyword="转债")) == 24


def test_keyword_like_wildcards_are_escaped(repo):
    repo.add(make_record(bond_name="100%稳赚转债"))
    repo.add(make_record(bond_name="A_1转债"))
    # 「%」按字面匹配，不展开为通配符
    assert repo.count_filtered(RecordQuery(keyword="100%稳赚")) == 1
    assert repo.count_filtered(RecordQuery(keyword="_1转")) == 1
    assert repo.count_filtered(RecordQuery(keyword="稳赚转债")) == 1


def test_year_filter_crosses_years_correctly(repo):
    seed_page_records(repo)
    assert repo.count_filtered(RecordQuery(year=2025)) == 2
    assert repo.count_filtered(RecordQuery(year=2026)) == 23


def test_year_month_filter(repo):
    seed_page_records(repo)
    assert repo.count_filtered(RecordQuery(year=2026, month=3)) == 2
    assert repo.count_filtered(RecordQuery(year=2025, month=12)) == 1
    assert repo.count_filtered(RecordQuery(year=2026, month=2)) == 0


def test_month_without_year_means_all_year(repo):
    seed_page_records(repo)
    assert repo.count_filtered(RecordQuery(month=3)) == 25  # month 仅在选定年份时生效


def test_sort_by_price_and_profit(repo):
    repo.add(make_record(sale_price=Decimal("120.00"), quantity=10))  # 收益 200
    repo.add(make_record(sale_price=Decimal("130.00"), quantity=10))  # 收益 300
    repo.add(make_record(sale_price=Decimal("110.00"), quantity=50))  # 收益 500

    by_price = repo.list_page(RecordQuery(sort_key="price"), 0, 10)
    assert by_price[0].sale_price == Decimal("130.00")

    by_profit = repo.list_page(RecordQuery(sort_key="profit"), 0, 10)
    assert by_profit[0].sale_price == Decimal("110.00")  # 收益最高在前

    by_profit_asc = repo.list_page(RecordQuery(sort_key="profit", descending=False), 0, 10)
    assert by_profit_asc[0].sale_price == Decimal("120.00")


def test_sort_fallback_for_unknown_key(repo):
    seed_page_records(repo)
    unknown = repo.list_page(RecordQuery(sort_key="1; DROP TABLE sales"), 0, 100)
    assert [r.id for r in unknown] == [r.id for r in repo.list_all()]
    assert repo.count() == 25  # 表未被破坏


def test_filtered_sort_combination_stable(repo):
    seed_page_records(repo)
    query = RecordQuery(keyword="转债", year=2026, month=1, sort_key="price")
    records = repo.list_page(query, 0, 20)
    prices = [r.sale_price for r in records]
    assert prices == sorted(prices, reverse=True)
    assert all(r.sale_date.year == 2026 and r.sale_date.month == 1 for r in records)


def test_distinct_years_desc(repo):
    seed_page_records(repo)
    assert repo.distinct_years() == [2026, 2025]


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
