"""服务层集成测试：校验→事务写入协调、失败不假装成功。"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal

import pytest

from bond_profit.application.sales_service import SalesService
from bond_profit.domain.models import SaleRecord
from bond_profit.infrastructure.database import connect
from bond_profit.infrastructure.repository import RepositoryError, SalesRepository


@pytest.fixture()
def service(tmp_path):
    conn = connect(tmp_path / "app.db")
    yield SalesService(SalesRepository(conn))
    conn.close()


def make_record(**overrides) -> SaleRecord:
    defaults = dict(
        bond_name="平银转债",
        bond_code="012345",
        sale_date=date(2026, 1, 15),
        sale_price=Decimal("130.00"),
        quantity=10,
        note="",
    )
    defaults.update(overrides)
    return SaleRecord(**defaults)


def test_create_valid_record_persists(service):
    result = service.create_record(make_record())
    assert result.ok
    assert service.list_records() == [result.record]


def test_create_invalid_record_rejected_and_not_saved(service):
    result = service.create_record(make_record(bond_code="12"))
    assert not result.ok
    assert result.errors
    assert service.list_records() == []


def test_rec01_duplicate_records_allowed_via_service(service):
    first = service.create_record(make_record())
    second = service.create_record(make_record())
    assert first.ok and second.ok
    assert first.record.id != second.record.id
    assert len(service.list_records()) == 2


def test_create_normalizes_name_and_note(service):
    result = service.create_record(make_record(bond_name="  平银转债  ", note="   "))
    assert result.ok
    assert result.record.bond_name == "平银转债"
    assert result.record.note == ""


def test_update_record(service):
    created = service.create_record(make_record()).record
    created.sale_price = Decimal("110.00")
    result = service.update_record(created)
    assert result.ok
    assert service.list_records()[0].sale_price == Decimal("110.00")


def test_delete_record(service):
    created = service.create_record(make_record()).record
    service.delete_record(created.id)
    assert service.list_records() == []


def test_write_failure_returns_failure_and_saves_nothing(service):
    """用 authorizer 拒绝 INSERT 模拟数据库写入失败（§5.2）。"""

    def deny_insert(action, *_args):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_INSERT else sqlite3.SQLITE_OK

    service._repository._conn.set_authorizer(deny_insert)
    result = service.create_record(make_record())

    assert not result.ok
    assert result.failure  # 中文用户提示
    assert not result.errors
    assert service.list_records() == []


def test_delete_missing_record_raises(service):
    with pytest.raises(RepositoryError):
        service.delete_record(9999)


# ---- 分页查询（§3.3，页码钳制） ---------------------------------------------

from bond_profit.domain.models import RecordQuery  # noqa: E402


def test_list_page_returns_total_and_page(service):
    for i in range(21):
        service.create_record(make_record(bond_name=f"转债{i:02d}号"))
    result = service.list_page(RecordQuery(), page=1, page_size=20)
    assert len(result.records) == 20
    assert result.total == 21
    assert result.page == 1


def test_list_page_clamps_page_beyond_last(service):
    for i in range(21):
        service.create_record(make_record(bond_name=f"转债{i:02d}号"))
    result = service.list_page(RecordQuery(), page=99, page_size=20)
    assert result.page == 2
    assert len(result.records) == 1


def test_list_page_clamps_page_below_one(service):
    service.create_record(make_record())
    result = service.list_page(RecordQuery(), page=0, page_size=20)
    assert result.page == 1
    assert len(result.records) == 1


def test_list_page_empty_database(service):
    result = service.list_page(RecordQuery(), page=1, page_size=20)
    assert result.records == []
    assert result.total == 0
    assert result.page == 1


# ---- 全局统计（§3.2，STA-01 / REC-02） ---------------------------------------


def test_global_statistics_empty_database(service):
    stats = service.global_statistics()
    assert stats.total_count == 0
    assert stats.total_profit == Decimal("0")


def test_global_statistics_month_and_year_attribution(service):
    today = date.today()
    this_month = today.replace(day=1)
    prev_month = this_month - timedelta(days=1)  # 上月最后一天（可能是去年）
    service.create_record(make_record(sale_date=this_month, sale_price=Decimal("130.00")))  # +300
    service.create_record(make_record(sale_date=prev_month, sale_price=Decimal("110.00")))  # +100

    stats = service.global_statistics()
    assert stats.total_count == 2
    assert stats.total_profit == Decimal("400.00")
    assert stats.month_profit == Decimal("300.00")  # 只含本月
    expected_year = Decimal("400.00") if prev_month.year == today.year else Decimal("300.00")
    assert stats.year_profit == expected_year


def test_rec02_editing_date_moves_month_attribution(service):
    today = date.today()
    this_month = today.replace(day=1)
    prev_month = this_month - timedelta(days=1)

    created = service.create_record(
        make_record(sale_date=this_month, sale_price=Decimal("130.00"))
    ).record
    assert service.global_statistics().month_profit == Decimal("300.00")

    created.sale_date = prev_month  # 编辑历史日期 → 重新归属
    service.update_record(created)
    stats = service.global_statistics()
    assert stats.month_profit == Decimal("0")
    expected_year = Decimal("300.00") if prev_month.year == today.year else Decimal("0")
    assert stats.year_profit == expected_year
