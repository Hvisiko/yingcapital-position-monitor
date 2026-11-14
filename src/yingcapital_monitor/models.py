from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any


ZERO = Decimal("0")


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


@dataclass(frozen=True)
class Position:
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: Decimal
    unrealized_pnl: Decimal
    margin_type: str
    update_time: int | None = None

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.side}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": decimal_text(self.quantity),
            "entry_price": decimal_text(self.entry_price),
            "mark_price": decimal_text(self.mark_price),
            "leverage": decimal_text(self.leverage),
            "unrealized_pnl": decimal_text(self.unrealized_pnl),
            "margin_type": self.margin_type,
            "update_time": self.update_time,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Position":
        return cls(
            symbol=str(raw["symbol"]),
            side=str(raw["side"]),
            quantity=decimal_value(raw["quantity"]),
            entry_price=decimal_value(raw.get("entry_price")),
            mark_price=decimal_value(raw.get("mark_price")),
            leverage=decimal_value(raw.get("leverage")),
            unrealized_pnl=decimal_value(raw.get("unrealized_pnl")),
            margin_type=str(raw.get("margin_type", "UNKNOWN")),
            update_time=raw.get("update_time"),
        )


@dataclass(frozen=True)
class PositionEvent:
    action: str
    symbol: str
    side: str
    old_quantity: Decimal
    new_quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: Decimal
    unrealized_pnl: Decimal
    margin_type: str
    detected_at: str
    from_side: str | None = None

    @property
    def event_id(self) -> str:
        stable = "|".join(
            [
                self.action,
                self.symbol,
                self.side,
                self.from_side or "",
                decimal_text(self.old_quantity),
                decimal_text(self.new_quantity),
                decimal_text(self.entry_price),
                self.detected_at,
            ]
        )
        return sha256(stable.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        for key in (
            "old_quantity",
            "new_quantity",
            "entry_price",
            "mark_price",
            "leverage",
            "unrealized_pnl",
        ):
            raw[key] = decimal_text(raw[key])
        raw["event_id"] = self.event_id
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PositionEvent":
        return cls(
            action=str(raw["action"]),
            symbol=str(raw["symbol"]),
            side=str(raw["side"]),
            old_quantity=decimal_value(raw["old_quantity"]),
            new_quantity=decimal_value(raw["new_quantity"]),
            entry_price=decimal_value(raw.get("entry_price")),
            mark_price=decimal_value(raw.get("mark_price")),
            leverage=decimal_value(raw.get("leverage")),
            unrealized_pnl=decimal_value(raw.get("unrealized_pnl")),
            margin_type=str(raw.get("margin_type", "UNKNOWN")),
            detected_at=str(raw["detected_at"]),
            from_side=raw.get("from_side"),
        )


def parse_positions(rows: list[dict[str, Any]]) -> dict[str, Position]:
    positions: dict[str, Position] = {}
    for row in rows:
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue

        raw_amount = decimal_value(
            row.get("positionAmount", row.get("positionAmt", "0"))
        )
        raw_side = str(row.get("positionSide", "BOTH")).upper()
        if raw_side == "BOTH":
            side = "LONG" if raw_amount > 0 else "SHORT"
        else:
            side = raw_side
        quantity = abs(raw_amount)
        if quantity == 0:
            continue
        if side not in {"LONG", "SHORT"}:
            continue

        isolated = row.get("isolated", False)
        if isinstance(isolated, str):
            isolated = isolated.lower() == "true"
        position = Position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=decimal_value(row.get("entryPrice")),
            mark_price=decimal_value(row.get("markPrice")),
            leverage=decimal_value(row.get("leverage")),
            unrealized_pnl=decimal_value(row.get("unrealizedProfit")),
            margin_type="ISOLATED" if isolated else "CROSS",
            update_time=row.get("updateTime"),
        )
        positions[position.key] = position
    return positions

