from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    portfolio_id: str
    trader_name: str
    timezone: str
    state_path: Path
    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def from_env(cls, *, require_notifications: bool = True) -> "Settings":
        settings = cls(
            portfolio_id=os.getenv(
                "BINANCE_PORTFOLIO_ID", "5075281354358777856"
            ).strip(),
            trader_name=os.getenv("BINANCE_TRADER_NAME", "熬鹰资本").strip(),
            timezone=os.getenv("MONITOR_TIMEZONE", "America/New_York").strip(),
            state_path=Path(
                os.getenv("MONITOR_STATE_PATH", ".runtime/state.json")
            ),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        )
        settings.validate(require_notifications=require_notifications)
        return settings

    def validate(self, *, require_notifications: bool) -> None:
        if not self.portfolio_id.isdigit():
            raise ValueError("BINANCE_PORTFOLIO_ID 必须是数字")
        if not self.trader_name:
            raise ValueError("BINANCE_TRADER_NAME 不能为空")
        if not require_notifications:
            return

        missing: list[str] = []
        required = {
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_CHAT_ID": self.telegram_chat_id,
        }
        for name, value in required.items():
            if not value:
                missing.append(name)
        if missing:
            raise ValueError("缺少通知配置：" + ", ".join(missing))

