"""金额转换：业务层 Decimal（元），数据库层定点整数分。

对应文档 §2.1/§5.1：数据库存 sale_price_cents 避免浮点误差，
禁止使用二进制浮点直接计算或比较金钱。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

_TWO_PLACES = Decimal("0.01")
_HUNDRED = Decimal(100)


def yuan_to_cents(price: Decimal) -> int:
    """元转分。要求大于 0 且最多两位小数，否则抛出 ValueError。"""
    if price <= 0:
        raise ValueError("价格必须大于0")
    try:
        quantized = price.quantize(_TWO_PLACES)
    except InvalidOperation as exc:
        raise ValueError("价格数值无效") from exc
    if quantized != price:
        raise ValueError("价格最多两位小数")
    return int((quantized * _HUNDRED).to_integral_exact())


def cents_to_yuan(cents: int) -> Decimal:
    """分转元，返回恰好两位小数的 Decimal。"""
    return (Decimal(cents) / _HUNDRED).quantize(_TWO_PLACES)
