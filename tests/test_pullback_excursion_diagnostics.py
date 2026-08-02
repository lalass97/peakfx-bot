import pytest

from research.pullback_excursion_diagnostics import (
    TradeExcursion,
    split_by_side,
    summarize_excursions,
)


def loss(mfe_r: float, *, side: str = "long", mae_r: float = -1.0) -> TradeExcursion:
    return TradeExcursion(side=side, realized_r=-1.0, mfe_r=mfe_r, mae_r=mae_r)


def win(*, side: str = "long") -> TradeExcursion:
    return TradeExcursion(side=side, realized_r=1.5, mfe_r=1.5, mae_r=-0.2)


def test_marks_repair_candidate_only_when_rate_exceeds_half() -> None:
    trades = [loss(0.6) for _ in range(16)] + [loss(0.1) for _ in range(14)]
    summary = summarize_excursions(trades)
    assert summary.losses == 30
    assert summary.loss_mfe_ge_050_rate == pytest.approx(16 / 30)
    assert summary.decision == "repair_candidate"


def test_exactly_half_is_not_enough_for_repair_gate() -> None:
    trades = [loss(0.6) for _ in range(15)] + [loss(0.1) for _ in range(15)]
    summary = summarize_excursions(trades)
    assert summary.loss_mfe_ge_050_rate == pytest.approx(0.5)
    assert summary.decision == "inconclusive"


def test_marks_retire_candidate_when_sixty_percent_fail_to_reach_quarter_r() -> None:
    trades = [loss(0.1) for _ in range(18)] + [loss(0.3) for _ in range(12)]
    summary = summarize_excursions(trades)
    assert summary.loss_mfe_ge_025_rate == pytest.approx(0.4)
    assert summary.decision == "retire_candidate"


def test_small_samples_remain_inconclusive() -> None:
    summary = summarize_excursions([loss(0.8) for _ in range(10)])
    assert summary.decision == "inconclusive"


def test_winners_do_not_enter_loser_excursion_rates() -> None:
    trades = [loss(0.6) for _ in range(16)] + [loss(0.1) for _ in range(14)] + [win() for _ in range(50)]
    summary = summarize_excursions(trades)
    assert summary.trades == 80
    assert summary.losses == 30
    assert summary.loss_mfe_ge_050_rate == pytest.approx(16 / 30)


def test_reports_medians_for_losing_trades() -> None:
    summary = summarize_excursions([
        loss(0.1, mae_r=-0.4),
        loss(0.5, mae_r=-0.8),
        loss(0.9, mae_r=-1.2),
    ], minimum_losses=1)
    assert summary.median_loss_mfe_r == pytest.approx(0.5)
    assert summary.median_loss_mae_r == pytest.approx(-0.8)


def test_splits_long_and_short_without_mixing_directions() -> None:
    trades = (
        [loss(0.6, side="long") for _ in range(20)]
        + [loss(0.1, side="long") for _ in range(10)]
        + [loss(0.1, side="short") for _ in range(20)]
        + [loss(0.3, side="short") for _ in range(10)]
    )
    summaries = split_by_side(trades)
    assert summaries["long"].decision == "repair_candidate"
    assert summaries["short"].decision == "retire_candidate"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"minimum_losses": 0}, "minimum_losses"),
        ({"repair_rate_threshold": 1.1}, "repair_rate_threshold"),
        ({"retire_below_rate_threshold": -0.1}, "retire_below_rate_threshold"),
        ({"repair_mfe_threshold_r": 0.2, "retire_mfe_threshold_r": 0.25}, "repair threshold"),
    ],
)
def test_rejects_invalid_gate_configuration(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        summarize_excursions([], **kwargs)
