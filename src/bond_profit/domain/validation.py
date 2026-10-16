"""字段校验与标准化（文档 §2.1）。

校验返回中文错误信息列表，空列表表示通过；
所有校验只在领域层定义，UI 与服务层共用同一套规则。
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from bond_profit.domain.models import SaleRecord

_CODE_PATTERN = re.compile(r"^[0-9]{6}$")
_NAME_MAX = 50
_NOTE_MAX = 500
_TWO_PLACES = Decimal("0.01")


def normalize(record: SaleRecord) -> SaleRecord:
    """标准化：名称/备注去首尾空格；纯空格备注视为空字符串。返回新对象。"""
    note = record.note.strip()
    return SaleRecord(
        bond_name=record.bond_name.strip(),
        bond_code=record.bond_code.strip(),
        sale_date=record.sale_date,
        sale_price=record.sale_price,
        quantity=record.quantity,
        note=note,
        id=record.id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def validate_record(record: SaleRecord, *, today: date | None = None) -> list[str]:
    """校验一条记录，返回中文错误列表（空列表 = 通过）。"""
    errors: list[str] = []
    today = today if today is not None else date.today()

    name = record.bond_name.strip()
    if not name:
        errors.append("转债名称不能为空")
    elif len(name) > _NAME_MAX:
        errors.append(f"转债名称不能超过{_NAME_MAX}个字符")

    if not _CODE_PATTERN.fullmatch(record.bond_code.strip()):
        errors.append("转债代码必须是恰好六位数字")

    if record.sale_date > today:
        errors.append("卖出日期不能晚于今天")

    price = record.sale_price
    if price <= 0:
        errors.append("卖出价格必须大于0")
    else:
        try:
            if price.quantize(_TWO_PLACES) != price:
                errors.append("卖出价格最多两位小数")
        except ArithmeticError:
            errors.append("卖出价格数值无效")

    if not isinstance(record.quantity, int) or isinstance(record.quantity, bool) or record.quantity <= 0:
        errors.append("卖出数量必须是正整数")

    if len(record.note.strip()) > _NOTE_MAX:
        errors.append(f"备注不能超过{_NOTE_MAX}个字符")

    return errors
