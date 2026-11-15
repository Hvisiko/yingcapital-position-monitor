from __future__ import annotations

import unittest
from unittest.mock import patch

from yingcapital_monitor.binance import (
    BinanceClient,
    OperationDataUnavailable,
)


class BinanceClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = BinanceClient("5075281354358777856")
        self.detail = {
            "leadPortfolioId": 5075281354358777856,
            "nickname": "熬鹰资本",
            "positionShow": False,
        }

    def test_operations_are_independent_of_hidden_positions(self) -> None:
        history = {"indexValue": "123", "total": 0, "list": []}
        with patch.object(
            self.client, "_request", side_effect=[self.detail, history]
        ) as request:
            snapshot = self.client.fetch_operations()

        self.assertFalse(snapshot.detail["positionShow"])
        self.assertEqual(snapshot.order_rows, [])
        self.assertEqual(request.call_args_list[0].args[:2], ("GET", "lead-portfolio/detail"))
        self.assertEqual(
            request.call_args_list[1].args[:2],
            ("POST", "lead-portfolio/order-history"),
        )
        payload = request.call_args_list[1].args[2]
        self.assertEqual(payload["portfolioId"], "5075281354358777856")
        self.assertEqual(payload["pageSize"], 100)

    def test_null_operation_data_is_unavailable(self) -> None:
        with patch.object(
            self.client, "_request", side_effect=[self.detail, None]
        ):
            with self.assertRaises(OperationDataUnavailable):
                self.client.fetch_operations()

    def test_missing_list_is_unavailable(self) -> None:
        with patch.object(
            self.client,
            "_request",
            side_effect=[self.detail, {"total": 1, "list": None}],
        ):
            with self.assertRaises(OperationDataUnavailable):
                self.client.fetch_operations()


if __name__ == "__main__":
    unittest.main()
