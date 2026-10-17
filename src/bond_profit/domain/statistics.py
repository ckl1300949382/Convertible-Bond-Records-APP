"""全局统计聚合（文档 §3.2）：纯函数、Decimal 计算，可独立测试。

统计卡片为全局值：从全部记录聚合，不经过列表搜索/筛选条件（STA-01）。
年份/月份归属以卖出日期为准，编辑历史日期后重新聚合即重新归属（REC-02）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from bond_profit.domain.calculations import profit_per_record
from bond_profit.domain.models import SaleRecord


@dataclass(frozen=True)
class GlobalStatistics:
    """四张全局统计卡片的值（§3.2）。"""

    total_profit: Decimal  # 累计收益
    year_profit: Decimal  # 本年收益
    month_profit: Decimal  # 本月收益
    total_count: int  # 累计卖出笔数


def global_statistics(
    records: list[SaleRecord], today: date | None = None
) -> GlobalStatistics:
    """从记录列表聚合全局统计；today 可注入便于测试。"""
    today = today or date.today()
    total = Decimal("0")
    year_profit = Decimal("0")
    month_profit = Decimal("0")
    for record in records:
        profit = profit_per_record(record.sale_price, record.quantity)
        total += profit
        if record.sale_date.year == today.year:
            year_profit += profit
            if record.sale_date.month == today.month:
                month_profit += profit
    return GlobalStatistics(
        total_profit=total,
        year_profit=year_profit,
        month_profit=month_profit,
        total_count=len(records),
    )


def monthly_profits(records: list[SaleRecord], year: int) -> list[Decimal]:
    """某年 1—12 月的月度收益（§3.5）：固定 12 项，缺失月份为 0，可含负值。"""
    months = [Decimal("0")] * 12
    for record in records:
        if record.sale_date.year == year:
            months[record.sale_date.month - 1] += profit_per_record(
                record.sale_price, record.quantity
            )
    return months


def yearly_profits(records: list[SaleRecord]) -> list[tuple[int, Decimal]]:
    """各年份总收益（§3.5），按年份升序，可含负值。"""
    totals: dict[int, Decimal] = {}
    for record in records:
        year = record.sale_date.year
        totals[year] = totals.get(year, Decimal("0")) + profit_per_record(
            record.sale_price, record.quantity
        )
    return sorted(totals.items())
