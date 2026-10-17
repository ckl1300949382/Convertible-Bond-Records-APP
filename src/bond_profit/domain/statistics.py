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
