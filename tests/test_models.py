from __future__ import annotations

import unittest

from yingcapital_monitor.models import parse_orders


LIVE_OPEN_LONG = {
    "symbol": "BTCUSDT",
    "baseAsset": "BTC",
    "quoteAsset": "USDT",
    "side": "BUY",
    "type": "MARKET",
    "positionSide": "LONG",
    "executedQty": 9.079,
    "avgPrice": 63837.88902,
    "totalPnl": 0.0,
    "orderUpdateTime": 1794698499143,
    "orderTime": 1794698499143,
}


class OrderModelTests(unittest.TestCase):
    def test_live_1821_record_is_open_long(self) -> None:
        order = parse_orders([LIVE_OPEN_LONG])[0]
        self.assertEqual(order.action, "OPEN_LONG")
        self.assertEqual(order.symbol, "BTCUSDT")
        self.assertEqual(str(order.executed_qty), "9.079")

    def test_all_four_web_operation_mappings(self) -> None:
        cases = [
            ("BUY", "LONG", "OPEN_LONG"),
            ("SELL", "SHORT", "OPEN_SHORT"),
            ("SELL", "LONG", "CLOSE_LONG"),
            ("BUY", "SHORT", "CLOSE_SHORT"),
        ]
        for index, (side, position_side, expected) in enumerate(cases):
            row = dict(
                LIVE_OPEN_LONG,
                side=side,
                positionSide=position_side,
                orderTime=1794698499143 + index,
                orderUpdateTime=1794698499143 + index,
            )
            with self.subTest(side=side, position_side=position_side):
                self.assertEqual(parse_orders([row])[0].action, expected)

    def test_fingerprint_ignores_later_pnl_correction(self) -> None:
        first = parse_orders([LIVE_OPEN_LONG])[0]
        changed = parse_orders([{**LIVE_OPEN_LONG, "totalPnl": 123.45}])[0]
        self.assertEqual(first.fingerprint, changed.fingerprint)

    def test_non_trade_rows_are_ignored(self) -> None:
        self.assertEqual(
            parse_orders([{**LIVE_OPEN_LONG, "executedQty": 0}]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
