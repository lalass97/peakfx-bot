from __future__ import annotations

import pandas as pd

from paper.execution_reconciliation import reconcile_trades, reconciliation_summary


def _modeled() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "entry_time": "2026-07-01T10:00:00Z",
                "side": 1,
                "entry": 1.1000,
                "exit_time": "2026-07-01T15:00:00Z",
                "exit": 1.1030,
                "pnl": 30.0,
            },
            {
                "entry_time": "2026-07-02T11:00:00Z",
                "side": -1,
                "entry": 1.1050,
                "exit_time": "2026-07-02T14:00:00Z",
                "exit": 1.1070,
                "pnl": -20.0,
            },
        ]
    )


def test_reconcile_matches_by_side_and_nearest_time() -> None:
    live = pd.DataFrame(
        [
            {
                "entry_time": "2026-07-01T10:05:00Z",
                "side": 1,
                "entry": 1.1001,
                "exit_time": "2026-07-01T15:03:00Z",
                "exit": 1.1028,
                "pnl": 27.0,
                "ticket": 101,
            },
            {
                "entry_time": "2026-07-02T11:02:00Z",
                "side": -1,
                "entry": 1.1049,
                "exit_time": "2026-07-02T14:01:00Z",
                "exit": 1.1072,
                "pnl": -23.0,
                "ticket": 102,
            },
        ]
    )

    result = reconcile_trades(_modeled(), live)
    assert list(result["status"]) == ["matched", "matched"]
    assert result.loc[0, "ticket"] == 101
    assert round(float(result.loc[0, "entry_slippage_pips"]), 6) == 1.0
    assert round(float(result.loc[0, "exit_slippage_pips"]), 6) == 2.0


def test_reconcile_marks_missed_and_unexpected_trades() -> None:
    live = pd.DataFrame(
        [
            {
                "entry_time": "2026-07-04T10:00:00Z",
                "side": 1,
                "entry": 1.1200,
                "exit_time": "2026-07-04T12:00:00Z",
                "exit": 1.1210,
                "pnl": 10.0,
                "ticket": 999,
            }
        ]
    )

    result = reconcile_trades(_modeled(), live)
    assert (result["status"] == "missed_live").sum() == 2
    assert (result["status"] == "unexpected_live").sum() == 1


def test_summary_becomes_critical_for_large_miss_rate() -> None:
    live = pd.DataFrame(
        [
            {
                "entry_time": "2026-07-01T10:01:00Z",
                "side": 1,
                "entry": 1.1000,
                "exit_time": "2026-07-01T15:00:00Z",
                "exit": 1.1030,
                "pnl": 30.0,
                "ticket": 101,
            }
        ]
    )

    summary = reconciliation_summary(reconcile_trades(_modeled(), live))
    assert summary["status"] == "critical"
    assert summary["matched_trades"] == 1
    assert summary["missed_live"] == 1
    assert summary["missed_trade_rate"] == 0.5
