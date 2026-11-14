from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yingcapital_monitor.app import run_monitor
from decimal import Decimal

from yingcapital_monitor.binance import BinanceSnapshot, PositionDataUnavailable
from yingcapital_monitor.config import Settings
from yingcapital_monitor.models import Position
from yingcapital_monitor.state import MonitorState, load_state, save_state


def settings(path: Path) -> Settings:
    return Settings(
        portfolio_id="5075281354358777856",
        trader_name="熬鹰资本",
        timezone="America/New_York",
        state_path=path,
        telegram_bot_token="test-token",
        telegram_chat_id="123456789",
    )


class MonitorSafetyTests(unittest.TestCase):
    @patch("yingcapital_monitor.app.BinanceClient.fetch_snapshot")
    def test_unavailable_data_never_replaces_existing_baseline(self, fetch) -> None:
        fetch.side_effect = PositionDataUnavailable("data=null")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = MonitorState(
                portfolio_id="5075281354358777856",
                initialized=True,
                initialized_at="2026-11-14T10:00:00-05:00",
                updated_at="2026-11-14T10:00:00-05:00",
            )
            save_state(path, original)

            exit_code = run_monitor(settings(path))
            restored = load_state(path, "5075281354358777856")

            self.assertEqual(exit_code, 0)
            self.assertTrue(restored.initialized)
            self.assertEqual(restored.updated_at, original.updated_at)
            self.assertEqual(restored.baseline, original.baseline)

    @patch("yingcapital_monitor.app.time.sleep")
    @patch("yingcapital_monitor.app.BinanceClient.fetch_snapshot")
    def test_unconfirmed_empty_snapshot_never_reports_close(
        self, fetch, _sleep
    ) -> None:
        old_position = Position(
            symbol="BTCUSDT",
            side="LONG",
            quantity=Decimal("1"),
            entry_price=Decimal("70000"),
            mark_price=Decimal("71000"),
            leverage=Decimal("10"),
            unrealized_pnl=Decimal("1000"),
            margin_type="CROSS",
        )
        fetch.side_effect = [
            BinanceSnapshot(
                detail={
                    "leadPortfolioId": "5075281354358777856",
                    "nickname": "熬鹰资本",
                    "positionShow": True,
                },
                position_rows=[],
            ),
            PositionDataUnavailable("第二次读取 data=null"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = MonitorState(
                portfolio_id="5075281354358777856",
                initialized=True,
                initialized_at="2026-11-14T10:00:00-05:00",
                updated_at="2026-11-14T10:00:00-05:00",
                baseline={old_position.key: old_position},
            )
            save_state(path, original)

            exit_code = run_monitor(settings(path))
            restored = load_state(path, "5075281354358777856")

            self.assertEqual(exit_code, 0)
            self.assertEqual(restored.baseline, original.baseline)
            self.assertEqual(restored.pending, [])


if __name__ == "__main__":
    unittest.main()
