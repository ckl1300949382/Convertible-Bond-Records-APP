"""销售记录领域模型。

对应文档 §2.1：每条记录表示一次实际卖出；
成本固定每张 100 元，无手续费；金额业务层使用 Decimal。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class SaleRecord:
    bond_name: str
    bond_code: str
    sale_date: date
    sale_price: Decimal
    quantity: int
    note: str = ""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class RecordQuery:
    """记录列表查询条件（§3.3 搜索/筛选/排序）。

    keyword 对名称或代码做包含匹配；year/month 为筛选（month 需配合 year）；
    sort_key 只允许 date/price/profit；默认最新日期在前（同日期按 id 降序）。
    """

    keyword: str = ""
    year: Optional[int] = None
    month: Optional[int] = None
    sort_key: str = "date"
    descending: bool = True
