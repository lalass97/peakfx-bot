from __future__ import annotations

import copy

import pytest

from research.validate_mt5_exp2_run import validate_run


def valid_payload(stage: str = "screen_12m") -> dict[str, object]:
    dates = {
        "smoke_1m": ("2025-06-01", "2025-06-30"),
        "screen_12m": ("2024-07-01", "2025-06-30"),
        "oos_6m": ("2025-07-01", "2025-12-31"),
    }
    start_date, end_date = dates[stage]
    return {
        "candidate_id": "peakfx_confirmed_breakout_exp2_v1_45",
        "stage": stage,
        "symbol": "EURUSD",
        "timeframe": "H1",
        "modeling": "every_tick_based_on_real_ticks",
        "start_date": start_date,
        "end_date": end_date,
        "deposit": 10000.0,
        "currency": "USD",
        "leverage": "1:100",
        "demo_only": True,
        "source_sha256": "a" * 64,
        "report_sha256": "b" * 64,
        "metrics": {
            "net_profit": 100.0,
            "profit_factor": 1.20,
            "expected_payoff": 2.0,
            "completed_trades": 40,
            "max_drawdown_percent": 5.0,
            "safety_violations": 0,
        },
    }


def test_accepts_exact_screen_contract() -> None:
    result = validate_run(valid_payload())
    assert result.valid is True
    assert result.errors == ()


@pytest.mark.parametrize("stage", ["smoke_1m", "screen_12m", "oos_6m"])
def test_accepts_declared_stage_dates(stage: str) -> None:
    assert validate_run(valid_payload(stage)).valid is True


@pytest.mark.parametrize(
    ("path", "value", "expected_error"),
    [
        (("candidate_id",), "other", "wrong_candidate_id"),
        (("stage",), "ten_year", "unsupported_stage"),
        (("symbol",), "GBPUSD", "wrong_symbol"),
        (("timeframe",), "M15", "wrong_timeframe"),
        (("modeling",), "open_prices_only", "wrong_modeling"),
        (("demo_only",), False, "demo_only_required"),
        (("source_sha256",), "bad", "invalid_source_sha256"),
        (("report_sha256",), "BAD" * 21 + "B", "invalid_report_sha256"),
        (("metrics", "completed_trades"), -1, "invalid_metric_type:completed_trades"),
        (("metrics", "profit_factor"), True, "invalid_metric_type:profit_factor"),
    ],
)
def test_rejects_tampered_run(path: tuple[str, ...], value: object, expected_error: str) -> None:
    payload = copy.deepcopy(valid_payload())
    target = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]
    result = validate_run(payload)
    assert result.valid is False
    assert expected_error in result.errors


def test_rejects_cherry_picked_dates() -> None:
    payload = valid_payload()
    payload["start_date"] = "2024-08-01"
    result = validate_run(payload)
    assert result.valid is False
    assert "wrong_start_date" in result.errors


def test_rejects_unknown_fields_and_metrics() -> None:
    payload = valid_payload()
    payload["optimized_after_test"] = True
    payload["metrics"]["custom_score"] = 999  # type: ignore[index]
    result = validate_run(payload)
    assert result.valid is False
    assert "unknown_field:optimized_after_test" in result.errors
    assert "unknown_metric:custom_score" in result.errors
