from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Position, PositionEvent


STATE_VERSION = 1


@dataclass
class PendingNotification:
    event: PositionEvent
    delivered: dict[str, bool] = field(
        default_factory=lambda: {"telegram": False}
    )

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event.to_dict(), "delivered": self.delivered}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PendingNotification":
        delivered = raw.get("delivered", {})
        return cls(
            event=PositionEvent.from_dict(raw["event"]),
            delivered={
                "telegram": bool(delivered.get("telegram", False)),
            },
        )


@dataclass
class MonitorState:
    portfolio_id: str
    initialized: bool = False
    baseline: dict[str, Position] = field(default_factory=dict)
    pending: list[PendingNotification] = field(default_factory=list)
    initialized_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "portfolio_id": self.portfolio_id,
            "initialized": self.initialized,
            "initialized_at": self.initialized_at,
            "updated_at": self.updated_at,
            "baseline": {
                key: value.to_dict() for key, value in sorted(self.baseline.items())
            },
            "pending": [item.to_dict() for item in self.pending],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any], portfolio_id: str) -> "MonitorState":
        if raw.get("version") != STATE_VERSION:
            raise ValueError("不支持的状态文件版本")
        if str(raw.get("portfolio_id")) != portfolio_id:
            raise ValueError("状态文件的项目 ID 与当前配置不一致")
        return cls(
            portfolio_id=portfolio_id,
            initialized=bool(raw.get("initialized", False)),
            initialized_at=raw.get("initialized_at"),
            updated_at=raw.get("updated_at"),
            baseline={
                key: Position.from_dict(value)
                for key, value in raw.get("baseline", {}).items()
            },
            pending=[
                PendingNotification.from_dict(item)
                for item in raw.get("pending", [])
            ],
        )


def load_state(path: Path, portfolio_id: str) -> MonitorState:
    if not path.exists():
        return MonitorState(portfolio_id=portfolio_id)
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return MonitorState.from_dict(raw, portfolio_id)


def save_state(path: Path, state: MonitorState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

