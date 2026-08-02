import pytest

from research.pullback_configuration_contract import (
    PullbackConfiguration,
    validate_configuration,
    validated_configuration,
)


def test_recovered_baseline_defaults_are_valid() -> None:
    config = PullbackConfiguration()
    assert validated_configuration(config) is config


def test_validation_does_not_mutate_or_invent_fallbacks() -> None:
    config = PullbackConfiguration(risk_percent=0.3, max_spread_points=20)
    validated = validated_configuration(config)
    assert validated == config
    assert validated.risk_percent == 0.3
    assert validated.max_spread_points == 20


def test_live_trading_is_rejected() -> None:
    with pytest.raises(ValueError, match="live_trading_disabled"):
        validate_configuration(PullbackConfiguration(demo_only=False))


def test_disabled_stop_loss_is_rejected_without_hidden_lot_fallback() -> None:
    with pytest.raises(ValueError, match="stop_loss_required"):
        validate_configuration(PullbackConfiguration(stop_loss_enabled=False))


@pytest.mark.parametrize("risk_percent", [0.0, -0.01, 0.500001, 1.0, 100.0])
def test_risk_must_remain_inside_recovered_safety_cap(risk_percent: float) -> None:
    with pytest.raises(ValueError, match="risk_percent_out_of_bounds"):
        validate_configuration(PullbackConfiguration(risk_percent=risk_percent))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("atr_stop_multiplier", 0.0, "atr_stop_multiplier_invalid"),
        ("atr_stop_multiplier", -1.0, "atr_stop_multiplier_invalid"),
        ("reward_risk", 0.9999, "reward_risk_invalid"),
        ("setup_expiration_bars", 0, "setup_expiration_invalid"),
        ("setup_expiration_bars", -1, "setup_expiration_invalid"),
        ("max_spread_points", 0, "max_spread_invalid"),
        ("magic_number", 0, "magic_number_invalid"),
        ("magic_number", -1, "magic_number_invalid"),
    ],
)
def test_invalid_safety_inputs_fail_closed(field: str, value: float, message: str) -> None:
    kwargs = {field: value}
    with pytest.raises(ValueError, match=message):
        validate_configuration(PullbackConfiguration(**kwargs))


def test_boundary_values_are_accepted() -> None:
    validate_configuration(
        PullbackConfiguration(
            risk_percent=0.5,
            atr_stop_multiplier=0.0001,
            reward_risk=1.0,
            setup_expiration_bars=1,
            max_spread_points=1,
            magic_number=1,
        )
    )
