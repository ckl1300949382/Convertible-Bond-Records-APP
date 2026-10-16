"""收益计算规则（文档 §2.2，不可擅改）。

单笔收益 =（卖出单价 − 100.00）× 张数
利润可正、负或为 0，均计入统计；显示固定两位小数。
"""

from __future__ import annotations

from decimal import Decimal

COST_PER_UNIT = Decimal("100.00")
_TWO_PLACES = Decimal("0.01")


def profit_per_record(sale_price: Decimal, quantity: int) -> Decimal:
    """单笔收益，精确 Decimal 值（不限定小数位）。"""
    return (sale_price - COST_PER_UNIT) * quantity


def format_money(value: Decimal) -> str:
    """固定两位小数：正数带 + 号，0 无符号，负数带 − 号。"""
    quantized = value.quantize(_TWO_PLACES)
    if quantized == 0:  # 避免 Decimal('-0.00')
        return "0.00"
    if quantized > 0:
        return f"+{quantized}"
    return str(quantized)
