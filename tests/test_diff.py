from __future__ import annotations

import unittest
from decimal import Decimal

from yingcapital_monitor.diff import compare_positions
from yingcapital_monitor.models import Position, parse_positions


def position(symbol: str, side: str, quantity: str) -> Position:
    return Position(
        symbol=symbol,
        side=side,
        quantity=Decimal(quantity),
        entry_price=Decimal("100"),
        mark_price=Decimal("101"),
        leverage=Decimal("10"),
        unrealized_pnl=Decimal("1"),
        margin_type="CROSS",
    )


class ComparePositionsTests(unittest.TestCase):
    def test_open_add_reduce_close(self) -> None:
        empty: dict[str, Position] = {}
        one = {"BTCUSDT:LONG": position("BTCUSDT", "LONG", "1")}
        two = {"BTCUSDT:LONG": position("BTCUSDT", "LONG", "2")}
        half = {"BTCUSDT:LONG": position("BTCUSDT", "LONG", "0.5")}

        self.assertEqual(compare_positions(empty, one)[0].action, "OPEN")
        self.assertEqual(compare_positions(one, two)[0].action, "ADD")
        self.assertEqual(compare_positions(two, half)[0].action, "REDUCE")
        self.assertEqual(compare_positions(half, empty)[0].action, "CLOSE")

    def test_reverse_is_one_event(self) -> None:
        old = {"ETHUSDT:LONG": position("ETHUSDT", "LONG", "2")}
        new = {"ETHUSDT:SHORT": position("ETHUSDT", "SHORT", "3")}
        events = compare_positions(old, new, detected_at="2026-11-14T10:00:00-05:00")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, "REVERSE")
        self.assertEqual(events[0].from_side, "LONG")
        self.assertEqual(events[0].side, "SHORT")

    def test_mark_price_only_change_does_not_alert(self) -> None:
        old = {"BTCUSDT:LONG": position("BTCUSDT", "LONG", "1")}
        changed = position("BTCUSDT", "LONG", "1")
        object.__setattr__(changed, "mark_price", Decimal("120"))
        self.assertEqual(compare_positions(old, {changed.key: changed}), [])

    def test_parses_one_way_short_and_filters_zero(self) -> None:
        parsed = parse_positions(
            [
                {
                    "symbol": "BTCUSDT",
                    "positionSide": "BOTH",
                    "positionAmount": "-0.25",
                    "entryPrice": "70000",
                    "markPrice": "69000",
                    "leverage": 10,
                    "unrealizedProfit": "250",
                    "isolated": False,
                },
                {
                    "symbol": "ETHUSDT",
                    "positionSide": "LONG",
                    "positionAmount": "0",
                },
            ]
        )
        self.assertEqual(list(parsed), ["BTCUSDT:SHORT"])
        self.assertEqual(parsed["BTCUSDT:SHORT"].quantity, Decimal("0.25"))


if __name__ == "__main__":
    unittest.main()

