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

SKY_CL_OPEN_LONG = {
    "symbol": "CLUSDT",
    "baseAsset": "CL",
    "quoteAsset": "USDT",
    "side": "BUY",
    "type": "LIMIT",
    "positionSide": "LONG",
    "executedQty": 24.64,
    "avgPrice": 86.1,
    "totalPnl": 0.0,
    "orderUpdateTime": 1794838614665,
    "orderTime": 1794692560039,
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

    def test_operation_time_uses_same_row_update_time(self) -> None:
        order = parse_orders([SKY_CL_OPEN_LONG])[0]
        self.assertEqual(order.order_time, 1794692560039)
        self.assertEqual(order.order_update_time, 1794838614665)
        self.assertEqual(order.operation_time, 1794838614665)
        # 指纹必须继续匹配 monitor-state 中已经通知过的同一笔交易。
        self.assertEqual(
            order.fingerprint,
            "92e619002adb22e90f1c6f97e70324b48db7edeb0a70d28344c3a431aefc9305",
        )

    def test_operation_time_falls_back_when_update_time_is_missing(self) -> None:
        order = parse_orders(
            [{**SKY_CL_OPEN_LONG, "orderUpdateTime": None}]
        )[0]
        self.assertEqual(order.operation_time, 1794692560039)

    def test_non_trade_rows_are_ignored(self) -> None:
        self.assertEqual(
            parse_orders([{**LIVE_OPEN_LONG, "executedQty": 0}]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
