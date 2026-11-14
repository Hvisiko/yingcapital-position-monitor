from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .binance import BinanceClient, BinanceError, PositionDataUnavailable
from .config import Settings
from .diff import compare_positions
from .models import PositionEvent, parse_positions
from .notify import TelegramNotifier
from .state import PendingNotification, load_state, save_state


LOGGER = logging.getLogger("yingcapital_monitor")


def _now(timezone: str) -> str:
    try:
        selected_timezone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        LOGGER.warning("系统缺少时区 %s，检测时间回退为 UTC", timezone)
        selected_timezone = utc_timezone.utc
    return datetime.now(selected_timezone).isoformat(timespec="seconds")


def _quantity_signature(positions) -> dict[str, str]:
    return {key: str(value.quantity) for key, value in sorted(positions.items())}


def _confirm_positions(client: BinanceClient, first_positions):
    """用第二次独立读取排除短暂空列表、不完整列表和缓存抖动。"""
    time.sleep(2)
    confirmation = client.fetch_snapshot()
    confirmed = parse_positions(confirmation.position_rows)
    if _quantity_signature(first_positions) != _quantity_signature(confirmed):
        raise PositionDataUnavailable("连续两次仓位快照不一致")
    return confirmed


def _deliver_pending(state, state_path, notifier: TelegramNotifier) -> list[str]:
    errors: list[str] = []
    for item in list(state.pending):
        event_id = item.event.event_id
        if not item.delivered["telegram"]:
            try:
                notifier.send_telegram(item.event)
                item.delivered["telegram"] = True
                save_state(state_path, state)
                LOGGER.info("Telegram 已发送：%s", event_id)
            except Exception as error:  # 每个渠道独立重试
                errors.append(f"Telegram {event_id}: {type(error).__name__}")
                LOGGER.error("Telegram 通知失败：%s（详细错误已隐藏）", event_id)

    state.pending = [
        item for item in state.pending if not all(item.delivered.values())
    ]
    save_state(state_path, state)
    return errors


def run_monitor(settings: Settings) -> int:
    state = load_state(settings.state_path, settings.portfolio_id)
    notifier = TelegramNotifier(settings)

    # 先重试上次未完成的渠道；每个渠道有独立送达标记。
    delivery_errors = _deliver_pending(state, settings.state_path, notifier)

    client = BinanceClient(settings.portfolio_id)
    try:
        snapshot = client.fetch_snapshot()
    except PositionDataUnavailable as error:
        LOGGER.warning("仓位数据暂时不可用；保留原基准，不生成事件：%s", error)
        return 1 if delivery_errors else 0
    except BinanceError:
        LOGGER.exception("读取币安当前仓位失败；保留原基准，不生成事件")
        return 1

    actual_name = str(snapshot.detail.get("nickname", "")).strip()
    if actual_name and actual_name != settings.trader_name:
        LOGGER.error(
            "项目昵称不匹配：预期=%s，实际=%s", settings.trader_name, actual_name
        )
        return 1

    now = _now(settings.timezone)
    current = parse_positions(snapshot.position_rows)
    if not state.initialized:
        try:
            current = _confirm_positions(client, current)
        except (PositionDataUnavailable, BinanceError) as error:
            LOGGER.warning("首次基准确认失败；不建立基准、不发送提醒：%s", error)
            return 1 if delivery_errors else 0
        state.initialized = True
        state.initialized_at = now
        state.updated_at = now
        state.baseline = current
        save_state(settings.state_path, state)
        LOGGER.info("首次有效运行：已保存 %d 个当前仓位为基准，不发送提醒", len(current))
        return 1 if delivery_errors else 0

    events = compare_positions(state.baseline, current, detected_at=now)
    if events:
        try:
            current = _confirm_positions(client, current)
        except (PositionDataUnavailable, BinanceError) as error:
            LOGGER.warning("仓位变化二次确认失败；保留原基准、不发送提醒：%s", error)
            return 1 if delivery_errors else 0
        events = compare_positions(state.baseline, current, detected_at=now)
    state.baseline = current
    state.updated_at = now
    known_ids = {item.event.event_id for item in state.pending}
    for event in events:
        if event.event_id not in known_ids:
            state.pending.append(PendingNotification(event=event))
    # 先持久化新基准与待发事件，避免发送期间崩溃造成事件丢失。
    save_state(settings.state_path, state)

    if not events:
        LOGGER.info("当前仓位无变化，不发送消息")
        return 1 if delivery_errors else 0

    LOGGER.info("检测到 %d 个仓位变化", len(events))
    new_errors = _deliver_pending(state, settings.state_path, notifier)
    return 1 if delivery_errors or new_errors else 0


def check_api(settings: Settings) -> int:
    try:
        snapshot = BinanceClient(settings.portfolio_id).fetch_snapshot()
    except PositionDataUnavailable as error:
        LOGGER.warning("接口可访问，但仓位不可用：%s", error)
        return 2
    except BinanceError:
        LOGGER.exception("币安接口验证失败")
        return 1
    positions = parse_positions(snapshot.position_rows)
    LOGGER.info(
        "接口验证成功：nickname=%s，公开有效仓位=%d",
        snapshot.detail.get("nickname"),
        len(positions),
    )
    return 0


def send_test(settings: Settings) -> int:
    from decimal import Decimal

    event = PositionEvent(
        action="OPEN",
        symbol="TESTUSDT",
        side="LONG",
        old_quantity=Decimal("0"),
        new_quantity=Decimal("1"),
        entry_price=Decimal("100"),
        mark_price=Decimal("100"),
        leverage=Decimal("1"),
        unrealized_pnl=Decimal("0"),
        margin_type="CROSS",
        detected_at=_now(settings.timezone),
    )
    notifier = TelegramNotifier(settings)
    failed = False
    try:
        notifier.send_telegram(event)
        LOGGER.info("Telegram 测试通知已发送")
    except Exception:
        failed = True
        LOGGER.error("Telegram 测试通知失败（详细错误已隐藏）")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="熬鹰资本币安公开仓位监控")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check-api", action="store_true", help="只验证当前仓位接口")
    group.add_argument("--test-notification", action="store_true", help="发送 Telegram 测试通知")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_env(require_notifications=not args.check_api)
        if args.check_api:
            return check_api(settings)
        if args.test_notification:
            return send_test(settings)
        return run_monitor(settings)
    except Exception as error:
        LOGGER.error("程序执行失败：%s（详细错误已隐藏）", type(error).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())

