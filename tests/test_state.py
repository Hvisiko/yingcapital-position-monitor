from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from yingcapital_monitor.models import TradeEvent
from yingcapital_monitor.state import (
    MonitorState,
    PendingNotification,
    load_state,
    save_state,
)


PORTFOLIO_ID = "5075281354358777856"


def event() -> TradeEvent:
    return TradeEvent(
        order_fingerprint="abc123",
        action="OPEN_LONG",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        side="BUY",
        position_side="LONG",
        order_type="MARKET",
        executed_qty=Decimal("1"),
        avg_price=Decimal("100"),
        total_pnl=Decimal("0"),
        order_time=1000,
        order_update_time=1000,
    )


class StateTests(unittest.TestCase):
    def test_v1_position_state_migrates_to_fresh_operation_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "portfolio_id": PORTFOLIO_ID,
                        "initialized": True,
                        "baseline": {"BTCUSDT:LONG": {}},
                    }
                ),
                encoding="utf-8",
            )
            state = load_state(path, PORTFOLIO_ID)

        self.assertFalse(state.initialized)
        self.assertEqual(state.seen_order_fingerprints, [])

    def test_v2_operation_state_migrates_without_reset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "portfolio_id": PORTFOLIO_ID,
                        "initialized": True,
                        "initialized_at": "2026-11-14T23:21:02-05:00",
                        "updated_at": "2026-11-14T23:22:29-05:00",
                        "last_order_time": 1794698499143,
                        "seen_order_fingerprints": ["existing-first-trader"],
                        "pending": [],
                    }
                ),
                encoding="utf-8",
            )
            state = load_state(path, PORTFOLIO_ID)

        self.assertTrue(state.initialized)
        self.assertEqual(
            state.seen_order_fingerprints, ["existing-first-trader"]
        )
        self.assertEqual(state.last_order_time, 1794698499143)

    def test_v3_round_trip_includes_latest_record_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = MonitorState(
                portfolio_id=PORTFOLIO_ID,
                initialized=True,
                seen_order_fingerprints=["abc123"],
                pending=[PendingNotification(event=event())],
                initialized_at="2026-11-15T00:00:00-05:00",
                updated_at="2026-11-15T00:00:00-05:00",
                last_order_time=1000,
                latest_order_fingerprint="abc123",
                api_index_value="999",
            )
            save_state(path, original)
            restored = load_state(path, PORTFOLIO_ID)

        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_legacy_pending_both_action_is_made_unconfirmed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            legacy = event().to_dict()
            legacy.update(
                {
                    "action": "CLOSE_SHORT",
                    "position_side": "BOTH",
                }
            )
            path.write_text(
                json.dumps(
                    {
                        "version": 3,
                        "portfolio_id": PORTFOLIO_ID,
                        "initialized": True,
                        "seen_order_fingerprints": ["abc123"],
                        "pending": [
                            {
                                "event": legacy,
                                "delivered": {"telegram": False},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            restored = load_state(path, PORTFOLIO_ID)

        self.assertEqual(
            restored.pending[0].event.action,
            "DIRECTION_UNCONFIRMED",
        )
        self.assertEqual(restored.pending[0].event.order_fingerprint, "abc123")


if __name__ == "__main__":
    unittest.main()
