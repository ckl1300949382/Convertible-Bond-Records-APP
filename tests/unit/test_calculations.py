"""收益计算与金额转换测试（对应文档 §10.1 CAL-01～05）。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bond_profit.domain.calculations import format_money, profit_per_record
from bond_profit.domain.money import cents_to_yuan, yuan_to_cents


@pytest.mark.parametrize(
    ("price", "quantity", "expected"),
    [
        (Decimal("130.00"), 10, Decimal("300.00")),   # CAL-01
        (Decimal("100.01"), 10, Decimal("0.10")),     # CAL-02
        (Decimal("100.00"), 10, Decimal("0.00")),     # CAL-03
        (Decimal("98.50"), 10, Decimal("-15.00")),    # CAL-04
        (Decimal("125.50"), 20, Decimal("510.00")),   # CAL-05
    ],
)
def test_profit_per_record(price, quantity, expected):
    assert profit_per_record(price, quantity) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("300"), "+300.00"),
        (Decimal("0.10"), "+0.10"),
        (Decimal("0.00"), "0.00"),
        (Decimal("-15.00"), "-15.00"),
        (Decimal("-0.001"), "0.00"),
    ],
)
def test_format_money(value, expected):
    assert format_money(value) == expected


def test_yuan_to_cents():
    assert yuan_to_cents(Decimal("100.01")) == 10001
    assert yuan_to_cents(Decimal("0.01")) == 1
    assert yuan_to_cents(Decimal("125.5")) == 12550
    assert yuan_to_cents(Decimal("100")) == 10000


def test_yuan_to_cents_rejects_invalid():
    with pytest.raises(ValueError):
        yuan_to_cents(Decimal("0"))
    with pytest.raises(ValueError):
        yuan_to_cents(Decimal("-5.00"))
    with pytest.raises(ValueError):
        yuan_to_cents(Decimal("1.005"))  # 三位小数


def test_cents_to_yuan_roundtrip():
    assert cents_to_yuan(10001) == Decimal("100.01")
    assert cents_to_yuan(1) == Decimal("0.01")
    for cents in (1, 99, 10001, 999999):
        assert yuan_to_cents(cents_to_yuan(cents)) == cents
