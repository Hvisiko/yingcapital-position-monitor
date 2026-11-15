from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yingcapital_monitor.app import run_monitor
from yingcapital_monitor.binance import (
    BinanceOperationsSnapshot,
    OperationDataUnavailable,
)
from yingcapital_monitor.config import Settings
from yingcapital_monitor.state import MonitorState, load_state, save_state


PORTFOLIO_ID = "5075281354358777856"
LIVE_1821_ORDER = {
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


def settings(path: Path) -> Settings:
    return Settings(
        portfolio_id=PORTFOLIO_ID,
        trader_name="熬鹰资本",
        timezone="America/New_York",
        state_path=path,
        telegram_bot_token="not-a-real-token",
        telegram_chat_id="6545798564",
    )


def snapshot(rows: list[dict]) -> BinanceOperationsSnapshot:
    return BinanceOperationsSnapshot(
        detail={
            "leadPortfolioId": int(PORTFOLIO_ID),
            "nickname": "熬鹰资本",
            "positionShow": False,
        },
        order_rows=rows,
        total=len(rows),
        index_value=str(max((row["orderTime"] for row in rows), default=0)),
    )


class MonitorTests(unittest.TestCase):
    def test_baseline_then_real_new_trade_sends_once(self) -> None:
        new_close_long = {
            **LIVE_1821_ORDER,
            "side": "SELL",
            "positionSide": "LONG",
            "executedQty": 2.5,
            "avgPrice": 64000.0,
            "totalPnl": 405.27,
            "orderTime": LIVE_1821_ORDER["orderTime"] + 300_000,
            "orderUpdateTime": LIVE_1821_ORDER["orderTime"] + 300_000,
        }
        first = snapshot([LIVE_1821_ORDER])
        changed = snapshot([new_close_long, LIVE_1821_ORDER])

        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            configured = settings(state_path)
            with (
                patch(
                    "yingcapital_monitor.app.BinanceClient.fetch_operations",
                    side_effect=[first, changed, changed],
                ),
                patch(
                    "yingcapital_monitor.app.TelegramNotifier.send_telegram"
                ) as send,
            ):
                self.assertEqual(run_monitor(configured), 0)
                send.assert_not_called()

                self.assertEqual(run_monitor(configured), 0)
                self.assertEqual(send.call_count, 1)
                sent_event = send.call_args.args[0]
                self.assertEqual(sent_event.action, "CLOSE_LONG")
                self.assertEqual(sent_event.symbol, "BTCUSDT")

                self.assertEqual(run_monitor(configured), 0)
                self.assertEqual(send.call_count, 1)

            stored = load_state(state_path, PORTFOLIO_ID)
            self.assertTrue(stored.initialized)
            self.assertEqual(len(stored.seen_order_fingerprints), 2)
            self.assertEqual(stored.pending, [])

    def test_unavailable_operation_api_preserves_initialized_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            original = MonitorState(
                portfolio_id=PORTFOLIO_ID,
                initialized=True,
                seen_order_fingerprints=["existing"],
                initialized_at="2026-11-14T20:00:00-05:00",
                updated_at="2026-11-14T20:00:00-05:00",
                last_order_time=123,
            )
            save_state(state_path, original)
            before = json.loads(state_path.read_text(encoding="utf-8"))

            with (
                patch(
                    "yingcapital_monitor.app.BinanceClient.fetch_operations",
                    side_effect=OperationDataUnavailable("data=null"),
                ),
                patch("yingcapital_monitor.app.TelegramNotifier.send_telegram"),
            ):
                self.assertEqual(run_monitor(settings(state_path)), 1)

            after = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
