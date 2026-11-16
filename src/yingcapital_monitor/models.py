from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any


ZERO = Decimal("0")

ACTION_LABELS = {
    "OPEN_LONG": "开多",
    "OPEN_SHORT": "开空",
    "CLOSE_LONG": "平多",
    "CLOSE_SHORT": "平空",
}

ACTION_BY_SIDE = {
    ("BUY", "LONG"): "OPEN_LONG",
    ("SELL", "SHORT"): "OPEN_SHORT",
    ("SELL", "LONG"): "CLOSE_LONG",
    ("BUY", "SHORT"): "CLOSE_SHORT",
}


def decimal_value(value: Any, *, default: Decimal = ZERO) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def integer_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class OrderRecord:
    symbol: str
    base_asset: str
    quote_asset: str
    side: str
    position_side: str
    order_type: str
    executed_qty: Decimal
    avg_price: Decimal
    total_pnl: Decimal
    order_time: int
    order_update_time: int

    @property
    def operation_time(self) -> int:
        """网页“最新操作记录”的成交时间，缺失时才回退到下单时间。"""
        return self.order_update_time if self.order_update_time > 0 else self.order_time

    @property
    def action(self) -> str | None:
        return ACTION_BY_SIDE.get((self.side, self.position_side))

    @property
    def fingerprint(self) -> str:
        # 公开接口没有 orderId。下列字段共同稳定标识一条已成交操作；不使用
        # totalPnl，避免币安事后修正盈亏数值造成重复提醒。
        stable = {
            "symbol": self.symbol,
            "side": self.side,
            "positionSide": self.position_side,
            "type": self.order_type,
            "executedQty": decimal_text(self.executed_qty),
            "avgPrice": decimal_text(self.avg_price),
            "orderTime": self.order_time,
            "orderUpdateTime": self.order_update_time,
        }
        canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    def to_event(self) -> "TradeEvent":
        action = self.action
        if action is None:
            raise ValueError(
                f"无法识别操作类型：side={self.side}, positionSide={self.position_side}"
            )
        return TradeEvent(
            order_fingerprint=self.fingerprint,
            action=action,
            symbol=self.symbol,
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            side=self.side,
            position_side=self.position_side,
            order_type=self.order_type,
            executed_qty=self.executed_qty,
            avg_price=self.avg_price,
            total_pnl=self.total_pnl,
            order_time=self.order_time,
            order_update_time=self.order_update_time,
        )


@dataclass(frozen=True)
class TradeEvent:
    order_fingerprint: str
    action: str
    symbol: str
    base_asset: str
    quote_asset: str
    side: str
    position_side: str
    order_type: str
    executed_qty: Decimal
    avg_price: Decimal
    total_pnl: Decimal
    order_time: int
    order_update_time: int

    @property
    def operation_time(self) -> int:
        """网页“最新操作记录”的成交时间，缺失时才回退到下单时间。"""
        return self.order_update_time if self.order_update_time > 0 else self.order_time

    @property
    def event_id(self) -> str:
        return self.order_fingerprint

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_fingerprint": self.order_fingerprint,
            "action": self.action,
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "side": self.side,
            "position_side": self.position_side,
            "order_type": self.order_type,
            "executed_qty": decimal_text(self.executed_qty),
            "avg_price": decimal_text(self.avg_price),
            "total_pnl": decimal_text(self.total_pnl),
            "order_time": self.order_time,
            "order_update_time": self.order_update_time,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TradeEvent":
        return cls(
            order_fingerprint=str(raw["order_fingerprint"]),
            action=str(raw["action"]),
            symbol=str(raw["symbol"]),
            base_asset=str(raw.get("base_asset", "")),
            quote_asset=str(raw.get("quote_asset", "USDT")),
            side=str(raw["side"]),
            position_side=str(raw["position_side"]),
            order_type=str(raw.get("order_type", "UNKNOWN")),
            executed_qty=decimal_value(raw["executed_qty"]),
            avg_price=decimal_value(raw.get("avg_price")),
            total_pnl=decimal_value(raw.get("total_pnl")),
            order_time=integer_value(raw["order_time"]),
            order_update_time=integer_value(raw.get("order_update_time")),
        )


def parse_orders(rows: list[dict[str, Any]]) -> list[OrderRecord]:
    orders: list[OrderRecord] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        side = str(row.get("side", "")).strip().upper()
        position_side = str(row.get("positionSide", "")).strip().upper()
        executed_qty = abs(decimal_value(row.get("executedQty")))
        order_time = integer_value(row.get("orderTime"))

        # 无法稳定标识或不是实际成交的行不进入基准，也不会产生误报。
        if (
            not symbol
            or side not in {"BUY", "SELL"}
            or position_side not in {"LONG", "SHORT"}
            or executed_qty == 0
            or order_time <= 0
        ):
            continue

        orders.append(
            OrderRecord(
                symbol=symbol,
                base_asset=str(row.get("baseAsset", "")).strip().upper(),
                quote_asset=str(row.get("quoteAsset", "")).strip().upper(),
                side=side,
                position_side=position_side,
                order_type=str(row.get("type", "UNKNOWN")).strip().upper(),
                executed_qty=executed_qty,
                avg_price=decimal_value(row.get("avgPrice")),
                total_pnl=decimal_value(row.get("totalPnl")),
                order_time=order_time,
                order_update_time=integer_value(
                    row.get("orderUpdateTime", order_time)
                ),
            )
        )
    return orders
