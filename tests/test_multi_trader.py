from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from yingcapital_monitor.config import DEFAULT_TRADERS, Settings
from yingcapital_monitor.models import TradeEvent
from yingcapital_monitor.notify import _format_order_time, render_event


class MultiTraderConfigurationTests(unittest.TestCase):
    def test_seven_default_traders_have_unique_state_files(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings_list = Settings.all_from_env(require_notifications=False)

        self.assertEqual(
            [(item.portfolio_id, item.trader_name) for item in settings_list],
            list(DEFAULT_TRADERS),
        )
        self.assertEqual(len(settings_list), 7)
        self.assertEqual(len({item.state_path for item in settings_list}), 7)

    def test_telegram_message_contains_required_trade_fields(self) -> None:
        settings = Settings(
            portfolio_id="4532994172262753536",
            trader_name="Sky株式会社",
            timezone="America/New_York",
            state_path=Path(".runtime/test.json"),
            telegram_bot_token="token",
            telegram_chat_id="chat",
        )
        event = TradeEvent(
            order_fingerprint="sky-event",
            action="OPEN_SHORT",
            symbol="TSLAUSDT",
            base_asset="TSLA",
            quote_asset="USDT",
            side="SELL",
            position_side="SHORT",
            order_type="LIMIT",
            executed_qty=Decimal("1.89"),
            avg_price=Decimal("392"),
            total_pnl=Decimal("0"),
            order_time=1794707295278,
            order_update_time=1794783638495,
        )

        message = render_event(event, settings)
        self.assertIn("交易员：Sky株式会社", message)
        self.assertIn("交易对：TSLAUSDT", message)
        self.assertIn("操作方向：开空（空）", message)
        self.assertIn("成交价格：392 USDT", message)
        self.assertIn("成交数量：1.89", message)
        self.assertIn("成交价值：740.88 USDT", message)
        self.assertIn("操作时间：", message)

    def test_sky_cl_trade_uses_fill_update_time_shown_by_binance(self) -> None:
        settings = Settings(
            portfolio_id="4532994172262753536",
            trader_name="Sky株式会社",
            timezone="America/New_York",
            state_path=Path(".runtime/test.json"),
            telegram_bot_token="token",
            telegram_chat_id="chat",
        )
        event = TradeEvent(
            order_fingerprint="existing-sky-cl-event",
            action="OPEN_LONG",
            symbol="CLUSDT",
            base_asset="CL",
            quote_asset="USDT",
            side="BUY",
            position_side="LONG",
            order_type="LIMIT",
            executed_qty=Decimal("24.64"),
            avg_price=Decimal("86.1"),
            total_pnl=Decimal("0"),
            order_time=1794692560039,
            order_update_time=1794838614665,
        )

        message = render_event(event, settings)
        self.assertIn("操作方向：开多（多）", message)
        self.assertIn("成交价格：86.1 USDT", message)
        self.assertIn("成交数量：24.64", message)
        self.assertIn("操作时间：2026-11-16T09:16:54-05:00", message)
        self.assertNotIn("2026-11-14T16:42:40-05:00", message)

    def test_new_york_timezone_observes_daylight_saving_time(self) -> None:
        winter = _format_order_time(1794838614665, "America/New_York")
        summer = _format_order_time(1784131200000, "America/New_York")
        self.assertEqual(winter, "2026-11-16T09:16:54-05:00")
        self.assertEqual(summer, "2026-07-15T12:00:00-04:00")

    def test_one_way_mode_message_uses_action_direction(self) -> None:
        settings = Settings(
            portfolio_id="5293752834070546944",
            trader_name="Luke2019",
            timezone="America/New_York",
            state_path=Path(".runtime/test.json"),
            telegram_bot_token="token",
            telegram_chat_id="chat",
        )
        event = TradeEvent(
            order_fingerprint="luke-close-short",
            action="CLOSE_SHORT",
            symbol="SAMSUNGUSDT",
            base_asset="SAMSUNG",
            quote_asset="USDT",
            side="BUY",
            position_side="BOTH",
            order_type="MARKET",
            executed_qty=Decimal("60"),
            avg_price=Decimal("155.5858166"),
            total_pnl=Decimal("246.33863739"),
            order_time=1794543699679,
            order_update_time=1794543699679,
        )

        message = render_event(event, settings)
        self.assertIn("交易员：Luke2019", message)
        self.assertIn("操作方向：平空（空）", message)


if __name__ == "__main__":
    unittest.main()
