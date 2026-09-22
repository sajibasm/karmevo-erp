from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from erp.shared.money import Money


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        ("10.005", "BDT", "10.01"),
        ("10.004", "BDT", "10.00"),
        ("1234.5", "JPY", "1235"),
        ("1.0005", "KWD", "1.001"),
    ],
)
def test_quantize_uses_currency_minor_units(amount, currency, expected):
    assert Money.quantize(Decimal(amount), currency) == Decimal(expected)


def test_rounding_mode_is_explicit():
    rounded = Money.quantize(Decimal("10.005"), "BDT", ROUND_HALF_EVEN)

    assert rounded == Decimal("10.00")


def test_unknown_currency_is_rejected():
    with pytest.raises(ValueError, match="unsupported currency"):
        Money.quantize(Decimal("1"), "XYZ")
