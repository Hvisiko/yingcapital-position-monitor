from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from yingcapital_monitor.models import Position
from yingcapital_monitor.state import MonitorState, load_state, save_state


class StateTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = MonitorState(
                portfolio_id="5075281354358777856",
                initialized=True,
                baseline={
                    "BTCUSDT:LONG": Position(
                        symbol="BTCUSDT",
                        side="LONG",
                        quantity=Decimal("1.25"),
                        entry_price=Decimal("70000"),
                        mark_price=Decimal("71000"),
                        leverage=Decimal("10"),
                        unrealized_pnl=Decimal("1250"),
                        margin_type="CROSS",
                    )
                },
            )
            save_state(path, state)
            restored = load_state(path, "5075281354358777856")
            self.assertTrue(restored.initialized)
            self.assertEqual(
                restored.baseline["BTCUSDT:LONG"].quantity, Decimal("1.25")
            )


if __name__ == "__main__":
    unittest.main()

