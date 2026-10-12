"""余额响应解析。"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation


class BalanceResponseError(ValueError):
    """服务器返回了无法识别的余额数据。"""


def parse_balance_body(body: bytes) -> Decimal:
    """将接口返回的 JSON（形如 ``{"credit": 31.99}``）解析为余额。"""
    try:
        text = body.decode("utf-8").strip()
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BalanceResponseError("响应不是有效的 JSON") from exc
    if not isinstance(payload, dict) or "credit" not in payload:
        raise BalanceResponseError("响应缺少 credit 字段")
    try:
        value = Decimal(str(payload["credit"]))
    except (InvalidOperation, ValueError) as exc:
        raise BalanceResponseError("credit 不是有效数字") from exc
    if not value.is_finite():
        raise BalanceResponseError("余额不是有限数字")
    return value


def format_balance(value: Decimal) -> str:
    """余额固定显示三位小数。"""
    return f"{value:.6f}"
