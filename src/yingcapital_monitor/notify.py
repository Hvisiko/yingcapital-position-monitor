from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .models import ACTION_LABELS, TradeEvent, decimal_text


def _format_order_time(milliseconds: int, timezone_name: str) -> str:
    try:
        selected_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        selected_timezone = timezone.utc
    value = datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    return value.astimezone(selected_timezone).isoformat(timespec="seconds")


def render_event(event: TradeEvent, settings: Settings) -> str:
    action = ACTION_LABELS[event.action]
    direction = "多" if event.position_side == "LONG" else "空"
    quote_asset = event.quote_asset or "USDT"
    notional_value = event.executed_qty * event.avg_price
    return chr(10).join(
        [
            f"【{settings.trader_name}】{action}提醒",
            f"交易员：{settings.trader_name}",
            f"交易对：{event.symbol}",
            f"操作方向：{action}（{direction}）",
            f"成交价格：{decimal_text(event.avg_price)} {quote_asset}",
            f"成交数量：{decimal_text(event.executed_qty)}",
            f"成交价值：{decimal_text(notional_value)} {quote_asset}",
            f"订单类型：{event.order_type}",
            f"已实现盈亏：{decimal_text(event.total_pnl)} {quote_asset}",
            f"操作时间：{_format_order_time(event.operation_time, settings.timezone)}",
            f"项目 ID：{settings.portfolio_id}",
            "数据源：币安网页公开最新操作记录（只读）",
        ]
    )


class TelegramNotifier:
    def __init__(self, settings: Settings, *, timeout: float = 20) -> None:
        self.settings = settings
        self.timeout = timeout

    def send_telegram(self, event: TradeEvent) -> None:
        url = (
            "https://api.telegram.org/bot"
            f"{self.settings.telegram_bot_token}/sendMessage"
        )
        encoded = urllib.parse.urlencode(
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": render_event(event, self.settings),
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = urllib.request.Request(url=url, data=encoded, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict) or result.get("ok") is not True:
            description = (
                result.get("description") if isinstance(result, dict) else "响应无效"
            )
            raise RuntimeError(f"Telegram 发送失败：{description}")
