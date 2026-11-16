from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yingcapital_monitor.app import run_monitor, run_monitors
from yingcapital_monitor.binance import (
    BinanceOperationsSnapshot,
    OperationDataUnavailable,
)
from yingcapital_monitor.config import Settings
from yingcapital_monitor.state import MonitorState, load_state, save_state


TRADERS = (
    ("5075281354358777856", "熬鹰资本"),
    ("5296057151807357697", "请填写昵称"),
    ("5247756265911980544", "万箭穿心BTC"),
    ("4532994172262753536", "Sky株式会社"),
    ("5271501457743196416", "发烧好了呢"),
)

ROWS = {
    TRADERS[0][0]: {
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
    },
    TRADERS[1][0]: {
        "symbol": "UNITREEUSDT",
        "baseAsset": "UNITREE",
        "quoteAsset": "USDT",
        "side": "SELL",
        "type": "LIMIT",
        "positionSide": "SHORT",
        "executedQty": 487.24,
        "avgPrice": 102.4,
        "totalPnl": 0.0,
        "orderUpdateTime": 1794790003010,
        "orderTime": 1794789671487,
    },
    TRADERS[2][0]: {
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "side": "BUY",
        "type": "MARKET",
        "positionSide": "LONG",
        "executedQty": 1.5,
        "avgPrice": 62340.6166,
        "totalPnl": 0.0,
        "orderUpdateTime": 1794707894478,
        "orderTime": 1794707894478,
    },
    TRADERS[3][0]: {
        "symbol": "TSLAUSDT",
        "baseAsset": "TSLA",
        "quoteAsset": "USDT",
        "side": "SELL",
        "type": "LIMIT",
        "positionSide": "SHORT",
        "executedQty": 1.89,
        "avgPrice": 392.0,
        "totalPnl": 0.0,
        "orderUpdateTime": 1794783638495,
        "orderTime": 1794707295278,
    },
    TRADERS[4][0]: {
        "symbol": "SOXSUSDT",
        "baseAsset": "SOXS",
        "quoteAsset": "USDT",
        "side": "BUY",
        "type": "MARKET",
        "positionSide": "LONG",
        "executedQty": 1000.0,
        "avgPrice": 53.1745718,
        "totalPnl": 0.0,
        "orderUpdateTime": 1794668082533,
        "orderTime": 1794668082533,
    },
}


def make_settings(directory: Path) -> tuple[Settings, ...]:
    return tuple(
        Settings(
            portfolio_id=portfolio_id,
            trader_name=name,
            timezone="America/New_York",
            state_path=directory / f"{portfolio_id}.json",
            telegram_bot_token="not-a-real-token",
            telegram_chat_id="6545798564",
        )
        for portfolio_id, name in TRADERS
    )


def snapshot(
    portfolio_id: str,
    name: str,
    rows: list[dict],
) -> BinanceOperationsSnapshot:
    return BinanceOperationsSnapshot(
        detail={
            "leadPortfolioId": int(portfolio_id),
            "nickname": name,
            "positionShow": portfolio_id != TRADERS[0][0],
            "portfolioType": "SIGNAL",
        },
        order_rows=rows,
        total=len(rows),
        index_value=f"cursor-{portfolio_id}-{len(rows)}",
    )


class MonitorTests(unittest.TestCase):
    def test_five_traders_baselines_changes_and_dedup_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            settings_list = make_settings(Path(directory_name))
            current = {
                item.portfolio_id: snapshot(
                    item.portfolio_id,
                    item.trader_name,
                    [ROWS[item.portfolio_id]],
                )
                for item in settings_list
            }
            sent: list[tuple[str, object]] = []

            def fetch(client):
                return current[client.portfolio_id]

            def capture(notifier, event):
                sent.append((notifier.settings.portfolio_id, event))

            with (
                patch(
                    "yingcapital_monitor.app.BinanceClient.fetch_operations",
                    autospec=True,
                    side_effect=fetch,
                ),
                patch(
                    "yingcapital_monitor.app.TelegramNotifier.send_telegram",
                    autospec=True,
                    side_effect=capture,
                ),
            ):
                # 先模拟原有四位已存在的基准。
                self.assertEqual(run_monitors(settings_list[:4]), 0)
                self.assertEqual(sent, [])
                original_seen = {
                    item.portfolio_id: load_state(
                        item.state_path, item.portfolio_id
                    ).seen_order_fingerprints.copy()
                    for item in settings_list[:4]
                }

                # 加入第五位时，前四位不重置，第五位只建基准。
                self.assertEqual(run_monitors(settings_list), 0)
                self.assertEqual(sent, [])
                for item in settings_list[:4]:
                    state = load_state(item.state_path, item.portfolio_id)
                    self.assertEqual(
                        state.seen_order_fingerprints,
                        original_seen[item.portfolio_id],
                    )
                fifth_state = load_state(
                    settings_list[4].state_path, settings_list[4].portfolio_id
                )
                self.assertTrue(fifth_state.initialized)
                self.assertEqual(len(fifth_state.seen_order_fingerprints), 1)

                # 每位各增加一条，必须分别通知且互不覆盖。
                changed = {}
                action_sides = (
                    ("SELL", "LONG"),
                    ("BUY", "SHORT"),
                    ("SELL", "SHORT"),
                    ("BUY", "LONG"),
                    ("SELL", "LONG"),
                )
                for index, item in enumerate(settings_list, start=1):
                    old = ROWS[item.portfolio_id]
                    side, position_side = action_sides[index - 1]
                    new = {
                        **old,
                        "side": side,
                        "positionSide": position_side,
                        "executedQty": index,
                        "avgPrice": float(old["avgPrice"]) + index,
                        "orderTime": int(old["orderTime"]) + 600_000,
                        "orderUpdateTime": int(old["orderTime"]) + 600_000,
                    }
                    changed[item.portfolio_id] = snapshot(
                        item.portfolio_id,
                        item.trader_name,
                        [new, old],
                    )
                current = changed

                self.assertEqual(run_monitors(settings_list), 0)
                self.assertEqual(
                    {portfolio_id for portfolio_id, _ in sent},
                    {portfolio_id for portfolio_id, _ in TRADERS},
                )
                self.assertEqual(len(sent), 5)

                # 相同数据再次运行，不能重复通知。
                self.assertEqual(run_monitors(settings_list), 0)
                self.assertEqual(len(sent), 5)

            for item in settings_list:
                state = load_state(item.state_path, item.portfolio_id)
                self.assertEqual(len(state.seen_order_fingerprints), 2)
                self.assertIsNotNone(state.latest_order_fingerprint)
                self.assertIsNotNone(state.api_index_value)
                self.assertEqual(state.pending, [])

    def test_unavailable_one_trader_preserves_its_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            configured = make_settings(Path(directory_name))[0]
            original = MonitorState(
                portfolio_id=configured.portfolio_id,
                initialized=True,
                seen_order_fingerprints=["existing"],
                initialized_at="2026-11-14T20:00:00-05:00",
                updated_at="2026-11-14T20:00:00-05:00",
                last_order_time=123,
            )
            save_state(configured.state_path, original)
            before = json.loads(configured.state_path.read_text(encoding="utf-8"))

            with (
                patch(
                    "yingcapital_monitor.app.BinanceClient.fetch_operations",
                    side_effect=OperationDataUnavailable("data=null"),
                ),
                patch("yingcapital_monitor.app.TelegramNotifier.send_telegram"),
            ):
                self.assertEqual(run_monitor(configured), 1)

            after = json.loads(configured.state_path.read_text(encoding="utf-8"))
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
