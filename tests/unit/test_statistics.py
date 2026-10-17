"""全局统计聚合测试（§3.2 / STA-01 / REC-02）。today 注入保证确定性。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from bond_profit.domain.models import SaleRecord
from bond_profit.domain.statistics import global_statistics, monthly_profits, yearly_profits

TODAY = date(2026, 10, 17)


def make_record(**overrides) -> SaleRecord:
    defaults = dict(
        bond_name="平银转债",
        bond_code="012345",
        sale_date=date(2026, 10, 15),
        sale_price=Decimal("130.00"),
        quantity=10,
        note="",
    )
    defaults.update(overrides)
    return SaleRecord(**defaults)


def test_empty_records_all_zero():
    stats = global_statistics([], today=TODAY)
    assert stats.total_profit == Decimal("0")
    assert stats.year_profit == Decimal("0")
    assert stats.month_profit == Decimal("0")
    assert stats.total_count == 0


def test_attribution_current_month_counts_everywhere():
    records = [make_record()]  # 2026-10：收益 +300
    stats = global_statistics(records, today=TODAY)
    assert stats.total_profit == Decimal("300.00")
    assert stats.year_profit == Decimal("300.00")
    assert stats.month_profit == Decimal("300.00")
    assert stats.total_count == 1


def test_attribution_this_year_other_month():
    records = [make_record(sale_date=date(2026, 5, 1))]  # 本年非本月
    stats = global_statistics(records, today=TODAY)
    assert stats.total_profit == Decimal("300.00")
    assert stats.year_profit == Decimal("300.00")
    assert stats.month_profit == Decimal("0")
    assert stats.total_count == 1


def test_attribution_previous_year_excluded_from_year():
    records = [make_record(sale_date=date(2025, 10, 15))]  # 去年同月
    stats = global_statistics(records, today=TODAY)
    assert stats.total_profit == Decimal("300.00")
    assert stats.year_profit == Decimal("0")
    assert stats.month_profit == Decimal("0")
    assert stats.total_count == 1


def test_mixed_records_and_loss_accumulate():
    records = [
        make_record(),  # +300，本月
        make_record(sale_price=Decimal("98.50"), sale_date=date(2026, 9, 1)),  # −15，本年
        make_record(sale_price=Decimal("125.50"), quantity=20, sale_date=date(2025, 3, 1)),  # +510，去年
    ]
    stats = global_statistics(records, today=TODAY)
    assert stats.total_profit == Decimal("795.00")  # 300 − 15 + 510
    assert stats.year_profit == Decimal("285.00")  # 300 − 15
    assert stats.month_profit == Decimal("300.00")
    assert stats.total_count == 3


def test_rec02_edit_date_reattributes_to_new_year():
    """编辑卖出日期从 2025 改为 2026：两年汇总同步变化（REC-02）。"""
    records_2025 = [make_record(sale_date=date(2025, 6, 1))]
    records_2026 = [make_record(sale_date=date(2026, 6, 1))]
    old_stats = global_statistics(records_2025, today=TODAY)
    new_stats = global_statistics(records_2026, today=TODAY)
    assert old_stats.year_profit == Decimal("0")
    assert new_stats.year_profit == Decimal("300.00")
    assert old_stats.total_profit == new_stats.total_profit == Decimal("300.00")


# ---- 月度聚合（§3.5，STA-02 / STA-03） ---------------------------------------

def test_monthly_profits_empty_records_twelve_zeros():
    months = monthly_profits([], 2026)
    assert len(months) == 12
    assert all(value == Decimal("0") for value in months)


def test_monthly_profits_missing_months_are_zero():
    records = [make_record(sale_date=date(2026, 3, 15))]  # +300
    months = monthly_profits(records, 2026)
    assert months[2] == Decimal("300.00")  # 3 月
    assert months[0] == Decimal("0")  # 1 月缺失为 0（STA-02）
    assert sum(1 for value in months if value != 0) == 1


def test_monthly_profits_negative_month_counts_below_zero():
    records = [make_record(sale_price=Decimal("98.50"), sale_date=date(2026, 5, 1))]  # −15
    months = monthly_profits(records, 2026)
    assert months[4] == Decimal("-15.00")  # 负值保留（STA-03）


def test_monthly_profits_same_month_accumulates():
    records = [
        make_record(sale_date=date(2026, 8, 1), sale_price=Decimal("120.00")),  # +200
        make_record(sale_date=date(2026, 8, 20), sale_price=Decimal("98.50"), quantity=2),  # −3
    ]
    months = monthly_profits(records, 2026)
    assert months[7] == Decimal("197.00")


def test_monthly_profits_excludes_other_years():
    records = [make_record(sale_date=date(2025, 1, 20))]
    months = monthly_profits(records, 2026)
    assert all(value == Decimal("0") for value in months)


# ---- 年度聚合（§3.5） ---------------------------------------------------------

def test_yearly_profits_empty_records():
    assert yearly_profits([]) == []


def test_yearly_profits_ascending_order():
    records = [
        make_record(sale_date=date(2026, 1, 1)),  # +300
        make_record(sale_date=date(2024, 5, 1), sale_price=Decimal("98.50")),  # −15
        make_record(sale_date=date(2025, 9, 1), sale_price=Decimal("125.50"), quantity=20),  # +510
    ]
    years = yearly_profits(records)
    assert [year for year, _ in years] == [2024, 2025, 2026]  # 年份升序
    assert [value for _, value in years] == [
        Decimal("-15.00"),
        Decimal("510.00"),
        Decimal("300.00"),
    ]


def test_yearly_profits_same_year_accumulates():
    records = [
        make_record(sale_date=date(2026, 1, 1)),  # +300
        make_record(sale_date=date(2026, 6, 1), sale_price=Decimal("98.50")),  # −15
    ]
    years = yearly_profits(records)
    assert years == [(2026, Decimal("285.00"))]
