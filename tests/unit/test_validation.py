"""字段校验测试（对应文档 §10.1 VAL-01～07 及 §2.1 标准化规则）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from bond_profit.domain.models import SaleRecord
from bond_profit.domain.validation import normalize, validate_record

TODAY = date(2026, 10, 16)


def valid_record(**overrides) -> SaleRecord:
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


def test_valid_record_passes():
    assert validate_record(valid_record(), today=TODAY) == []


def test_val_01_code_keeps_leading_zeros():
    record = valid_record(bond_code="012345")
    assert validate_record(record, today=TODAY) == []


def test_val_02_code_wrong_length_rejected():
    assert validate_record(valid_record(bond_code="12345"), today=TODAY)
    assert validate_record(valid_record(bond_code="1234567"), today=TODAY)
    assert validate_record(valid_record(bond_code="12a456"), today=TODAY)


def test_val_03_price_zero_negative_three_decimals_rejected():
    errors = validate_record(valid_record(sale_price=Decimal("0")), today=TODAY)
    assert any("必须大于0" in e for e in errors)
    assert validate_record(valid_record(sale_price=Decimal("-1.00")), today=TODAY)
    errors = validate_record(
        valid_record(sale_price=Decimal("1.005")), today=TODAY
    )
    assert any("最多两位小数" in e for e in errors)


def test_val_04_quantity_invalid_rejected():
    for bad in (0, -1, 1.5):
        assert validate_record(valid_record(quantity=bad), today=TODAY)


def test_val_05_future_date_rejected():
    record = valid_record(sale_date=date(2026, 10, 17))
    errors = validate_record(record, today=TODAY)
    assert any("不能晚于今天" in e for e in errors)


def test_val_06_name_invalid_rejected():
    assert validate_record(valid_record(bond_name="   "), today=TODAY)
    assert validate_record(valid_record(bond_name="名" * 51), today=TODAY)


def test_val_07_note_too_long_rejected():
    record = valid_record(note="字" * 501)
    assert validate_record(record, today=TODAY)


def test_normalize_strips_and_empties_note():
    normalized = normalize(
        valid_record(bond_name="  平银转债  ", note="   ")
    )
    assert normalized.bond_name == "平银转债"
    assert normalized.note == ""
