from __future__ import annotations

import json
import urllib.parse
import urllib.request
from .config import Settings
from .models import PositionEvent, decimal_text


ACTION_LABELS = {
    "OPEN": "新开仓",
    "ADD": "加仓",
    "REDUCE": "减仓",
    "CLOSE": "平仓",
    "REVERSE": "反手",
}


def render_event(event: PositionEvent, settings: Settings) -> str:
    label = ACTION_LABELS[event.action]
    direction = (
        f"{event.from_side} → {event.side}"
        if event.action == "REVERSE"
        else event.side
    )
    lines = [
        f"【{settings.trader_name}】{label}提醒",
        f"合约：{event.symbol}",
        f"方向：{direction}",
        (
            "仓位数量："
            f"{decimal_text(event.old_quantity)} → {decimal_text(event.new_quantity)}"
        ),
        f"开仓均价：{decimal_text(event.entry_price)}",
        f"标记价格：{decimal_text(event.mark_price)}",
        f"杠杆：{decimal_text(event.leverage)}x",
        f"保证金模式：{event.margin_type}",
        f"未实现盈亏：{decimal_text(event.unrealized_pnl)} USDT",
        f"检测时间：{event.detected_at}",
        f"项目 ID：{settings.portfolio_id}",
        "数据源：币安公开当前仓位（只读）",
    ]
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, settings: Settings, *, timeout: float = 20) -> None:
        self.settings = settings
        self.timeout = timeout

    def send_telegram(self, event: PositionEvent) -> None:
        body = render_event(event, self.settings)
        url = (
            "https://api.telegram.org/bot"
            f"{self.settings.telegram_bot_token}/sendMessage"
        )
        encoded = urllib.parse.urlencode(
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": body,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = urllib.request.Request(url=url, data=encoded, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("ok") is not True:
            raise RuntimeError(f"Telegram 发送失败：{result.get('description')}")

