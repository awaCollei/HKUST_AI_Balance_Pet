from decimal import Decimal

import pytest

from balance_pet.balance import BalanceResponseError, format_balance, parse_balance_body


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b"12.3456", Decimal("12.3456")),
        (b"  8.2\r\n", Decimal("8.2")),
        (b"0", Decimal(0)),
        (b"-3.14", Decimal("-3.14")),
    ],
)
def test_parse_bare_number(body, expected):
    assert parse_balance_body(body) == expected


def test_format_balance():
    assert format_balance(Decimal("12.3")) == "12.300"
    assert format_balance(Decimal("12.3456")) == "12.346"


@pytest.mark.parametrize("body", [b"", b'{"credit": 1}', b"NaN", b"Infinity", b"12 CNY"])
def test_non_numeric_response_is_rejected(body):
    with pytest.raises(BalanceResponseError):
        parse_balance_body(body)
