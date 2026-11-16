from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TRADERS = (
    ("5075281354358777856", "熬鹰资本"),
    ("5296057151807357697", "请填写昵称"),
    ("5247756265911980544", "万箭穿心BTC"),
    ("4532994172262753536", "Sky株式会社"),
    ("5271501457743196416", "发烧好了呢"),
)


@dataclass(frozen=True)
class Settings:
    portfolio_id: str
    trader_name: str
    timezone: str
    state_path: Path
    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def all_from_env(
        cls, *, require_notifications: bool = True
    ) -> tuple["Settings", ...]:
        timezone = os.getenv("MONITOR_TIMEZONE", "America/New_York").strip()
        state_dir = Path(os.getenv("MONITOR_STATE_DIR", ".runtime"))
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        settings: list[Settings] = []
        for index, (default_id, default_name) in enumerate(DEFAULT_TRADERS, start=1):
            portfolio_id = os.getenv(
                f"BINANCE_TRADER_{index}_PORTFOLIO_ID", default_id
            ).strip()
            trader_name = os.getenv(
                f"BINANCE_TRADER_{index}_NAME", default_name
            ).strip()
            item = cls(
                portfolio_id=portfolio_id,
                trader_name=trader_name,
                timezone=timezone,
                state_path=state_dir / f"{portfolio_id}.json",
                telegram_bot_token=telegram_bot_token,
                telegram_chat_id=telegram_chat_id,
            )
            item.validate(require_notifications=require_notifications)
            settings.append(item)

        portfolio_ids = [item.portfolio_id for item in settings]
        if len(portfolio_ids) != len(set(portfolio_ids)):
            raise ValueError("五个交易员的项目 ID 不能重复")
        return tuple(settings)

    def validate(self, *, require_notifications: bool) -> None:
        if not self.portfolio_id.isdigit():
            raise ValueError("币安项目 ID 必须是数字")
        if not self.trader_name:
            raise ValueError("交易员名称不能为空")
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
