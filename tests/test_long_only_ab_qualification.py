import pytest

from research.long_only_ab_qualification import (
    ExperimentMetrics,
    LongOnlyABThresholds,
    qualify_long_only_ab,
)


def metrics(**overrides):
    values = dict(
        trade_count=500,
        net_profit=1000.0,
        profit_factor=1.30,
        maximum_drawdown_fraction=0.10,
        profitable_year_fraction=0.70,
        two_x_cost_net_profit=250.0,
        sequence_risk_decision="green",
    )
    values.update(overrides)
    return ExperimentMetrics(**values)


def test_promotes_only_when_candidate_clears_every_gate():
    baseline = metrics(net_profit=-245.50, profit_factor=0.98, maximum_drawdown_fraction=0.1378)
    candidate = metrics()

    report = qualify_long_only_ab(baseline, candidate)

    assert report.decision == "promote"
    assert report.failed_gates == ()
    assert report.net_profit_improvement == pytest.approx(1245.50)
    assert report.drawdown_improvement_fraction == pytest.approx(0.0378)


def test_positive_candidate_is_rejected_when_profit_factor_is_too_low():
    baseline = metrics(net_profit=-245.50, profit_factor=0.98, maximum_drawdown_fraction=0.1378)
    candidate = metrics(net_profit=350.0, profit_factor=1.08)

    report = qualify_long_only_ab(baseline, candidate)

    assert report.decision == "reject"
    assert "minimum_profit_factor" in report.failed_gates


def test_candidate_is_rejected_when_doubled_costs_remove_profit():
    baseline = metrics(net_profit=-245.50, profit_factor=0.98, maximum_drawdown_fraction=0.1378)
    candidate = metrics(two_x_cost_net_profit=-10.0)

    report = qualify_long_only_ab(baseline, candidate)

    assert report.decision == "reject"
    assert "positive_two_x_cost_net_profit" in report.failed_gates


def test_candidate_is_rejected_when_drawdown_is_worse():
    baseline = metrics(net_profit=-245.50, profit_factor=0.98, maximum_drawdown_fraction=0.1378)
    candidate = metrics(maximum_drawdown_fraction=0.15)

    report = qualify_long_only_ab(baseline, candidate)

    assert report.decision == "reject"
    assert "drawdown_not_worse" in report.failed_gates


def test_insufficient_sequence_evidence_is_inconclusive_when_other_metrics_pass():
    baseline = metrics(net_profit=-245.50, profit_factor=0.98, maximum_drawdown_fraction=0.1378)
    candidate = metrics(sequence_risk_decision="inconclusive")

    report = qualify_long_only_ab(baseline, candidate)

    assert report.decision == "inconclusive"
    assert report.failed_gates == ("green_sequence_risk",)


def test_trade_sample_cannot_be_reduced_below_declared_limit():
    baseline = metrics(trade_count=1000, net_profit=-245.50, profit_factor=0.98)
    candidate = metrics(trade_count=300)

    report = qualify_long_only_ab(
        baseline,
        candidate,
        LongOnlyABThresholds(maximum_trade_count_reduction_fraction=0.65),
    )

    assert report.decision == "reject"
    assert "trade_count_retention" in report.failed_gates


@pytest.mark.parametrize(
    "bad",
    [
        metrics(trade_count=0),
        metrics(net_profit=float("nan")),
        metrics(profit_factor=-1.0),
        metrics(maximum_drawdown_fraction=1.1),
        metrics(profitable_year_fraction=-0.1),
        metrics(sequence_risk_decision="unknown"),
    ],
)
def test_invalid_metrics_fail_closed(bad):
    with pytest.raises(ValueError):
        qualify_long_only_ab(metrics(), bad)
