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
