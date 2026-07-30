import pandas as pd

from paper.paper_trading_report import evaluate_gates, max_losing_streak, summarize_journal


def sample_journal() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticket": [1, 2, 3, 4],
            "entry_time": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"], utc=True),
            "exit_time": pd.to_datetime(["2026-01-01 02:00", "2026-01-02 02:00", "2026-01-03 02:00", "2026-01-04 02:00"], utc=True),
            "side": ["long", "short", "long", "short"],
            "entry": [1.1, 1.1, 1.1, 1.1],
            "exit": [1.101, 1.099, 1.098, 1.102],
            "volume": [0.1, 0.1, 0.1, 0.1],
            "pnl": [20.0, -10.0, -5.0, 30.0],
            "spread_points": [10, 11, 9, 12],
            "slippage_points": [1, 1, 2, 1],
            "reason": ["target", "stop", "stop", "target"],
        }
    )


def test_summary_metrics() -> None:
    summary = summarize_journal(sample_journal(), 10_000)
    assert summary["trades"] == 4
    assert summary["net_pnl"] == 35.0
    assert summary["win_rate_pct"] == 50.0
    assert summary["profit_factor"] > 3.0
    assert summary["max_losing_streak"] == 2


def test_max_losing_streak() -> None:
    assert max_losing_streak(pd.Series([-1, -2, 3, -4])) == 2


def test_gates_require_enough_trades() -> None:
    gates = evaluate_gates(summarize_journal(sample_journal(), 10_000))
    assert gates["enough_trades"] is False
    assert gates["positive_expectancy"] is True
