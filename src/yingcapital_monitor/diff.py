from __future__ import annotations

from datetime import datetime

from .models import Position, PositionEvent, ZERO


def _event(
    action: str,
    old: Position | None,
    new: Position | None,
    detected_at: str,
    *,
    from_side: str | None = None,
) -> PositionEvent:
    source = new or old
    if source is None:  # pragma: no cover - 调用方保证至少一个存在
        raise ValueError("old 和 new 不能同时为空")
    return PositionEvent(
        action=action,
        symbol=source.symbol,
        side=(new.side if new else old.side),
        old_quantity=(old.quantity if old else ZERO),
        new_quantity=(new.quantity if new else ZERO),
        entry_price=(new.entry_price if new else old.entry_price),
        mark_price=(new.mark_price if new else old.mark_price),
        leverage=(new.leverage if new else old.leverage),
        unrealized_pnl=(new.unrealized_pnl if new else old.unrealized_pnl),
        margin_type=(new.margin_type if new else old.margin_type),
        detected_at=detected_at,
        from_side=from_side,
    )


def compare_positions(
    old_positions: dict[str, Position],
    new_positions: dict[str, Position],
    *,
    detected_at: str | None = None,
) -> list[PositionEvent]:
    """比较两个有效快照；不会把“无数据”表示成空字典传入本函数。"""

    detected_at = detected_at or datetime.now().astimezone().isoformat()
    events: list[PositionEvent] = []
    handled: set[str] = set()

    symbols = sorted(
        {position.symbol for position in old_positions.values()}
        | {position.symbol for position in new_positions.values()}
    )

    for symbol in symbols:
        old_by_side = {
            position.side: position
            for position in old_positions.values()
            if position.symbol == symbol
        }
        new_by_side = {
            position.side: position
            for position in new_positions.values()
            if position.symbol == symbol
        }
        if len(old_by_side) == 1 and len(new_by_side) == 1:
            old_side, old_position = next(iter(old_by_side.items()))
            new_side, new_position = next(iter(new_by_side.items()))
            if old_side != new_side:
                events.append(
                    _event(
                        "REVERSE",
                        old_position,
                        new_position,
                        detected_at,
                        from_side=old_side,
                    )
                )
                handled.update({old_position.key, new_position.key})

    for key in sorted(set(old_positions) | set(new_positions)):
        if key in handled:
            continue
        old = old_positions.get(key)
        new = new_positions.get(key)
        if old is None and new is not None:
            events.append(_event("OPEN", None, new, detected_at))
        elif old is not None and new is None:
            events.append(_event("CLOSE", old, None, detected_at))
        elif old is not None and new is not None:
            if new.quantity > old.quantity:
                events.append(_event("ADD", old, new, detected_at))
            elif new.quantity < old.quantity:
                events.append(_event("REDUCE", old, new, detected_at))

    return events

