from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from yingcapital_monitor.binance import BinanceClient, PositionDataUnavailable


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class BinanceClientTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_null_positions_are_unavailable_not_empty(self, urlopen) -> None:
        urlopen.side_effect = [
            FakeResponse(
                {
                    "success": True,
                    "code": "000000",
                    "data": {
                        "leadPortfolioId": "5075281354358777856",
                        "nickname": "熬鹰资本",
                        "positionShow": False,
                    },
                }
            ),
            FakeResponse({"success": True, "code": "000000", "data": None}),
        ]
        with self.assertRaises(PositionDataUnavailable):
            BinanceClient("5075281354358777856").fetch_snapshot()

    @patch("urllib.request.urlopen")
    def test_explicit_empty_list_is_valid_snapshot(self, urlopen) -> None:
        urlopen.side_effect = [
            FakeResponse(
                {
                    "success": True,
                    "code": "000000",
                    "data": {
                        "leadPortfolioId": "5075281354358777856",
                        "nickname": "熬鹰资本",
                        "positionShow": True,
                    },
                }
            ),
            FakeResponse({"success": True, "code": "000000", "data": []}),
        ]
        snapshot = BinanceClient("5075281354358777856").fetch_snapshot()
        self.assertEqual(snapshot.position_rows, [])
        for call in urlopen.call_args_list:
            self.assertEqual(call.args[0].method, "GET")

    @patch("urllib.request.urlopen")
    def test_hidden_flag_rejects_even_an_empty_list(self, urlopen) -> None:
        urlopen.side_effect = [
            FakeResponse(
                {
                    "success": True,
                    "code": "000000",
                    "data": {
                        "leadPortfolioId": "5075281354358777856",
                        "nickname": "熬鹰资本",
                        "positionShow": False,
                    },
                }
            ),
            FakeResponse({"success": True, "code": "000000", "data": []}),
        ]
        with self.assertRaises(PositionDataUnavailable):
            BinanceClient("5075281354358777856").fetch_snapshot()


if __name__ == "__main__":
    unittest.main()

