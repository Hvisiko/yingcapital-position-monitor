from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from yingcapital_monitor.config import DEFAULT_TRADERS, Settings
from yingcapital_monitor.models import TradeEvent
from yingcapital_monitor.notify import render_event


class MultiTraderConfigurationTests(unittest.TestCase):
    def test_four_default_traders_have_unique_state_files(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings_list = Settings.all_from_env(require_notifications=False)

        self.assertEqual(
            [(item.portfolio_id, item.trader_name) for item in settings_list],
            list(DEFAULT_TRADERS),
        )
        self.assertEqual(len(settings_list), 4)
        self.assertEqual(len({item.state_path for item in settings_list}), 4)

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


if __name__ == "__main__":
    unittest.main()
