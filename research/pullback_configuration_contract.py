from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PullbackConfiguration:
    """Explicit research contract for safety-critical PeakFX inputs.

    This model intentionally rejects ambiguous or disabled protections instead of
    inventing fallback values. It does not submit or modify orders.
    """

    risk_percent: float = 0.25
    atr_stop_multiplier: float = 1.5
    reward_risk: float = 1.5
    setup_expiration_bars: int = 5
    max_spread_points: int = 25
    magic_number: int = 260142
    demo_only: bool = True
    stop_loss_enabled: bool = True


def validate_configuration(config: PullbackConfiguration) -> None:
    """Fail closed when a safety-critical input is invalid or ambiguous."""

    if not config.demo_only:
        raise ValueError("live_trading_disabled")
    if not config.stop_loss_enabled:
        raise ValueError("stop_loss_required")
    if not 0.0 < config.risk_percent <= 0.5:
        raise ValueError("risk_percent_out_of_bounds")
    if config.atr_stop_multiplier <= 0.0:
        raise ValueError("atr_stop_multiplier_invalid")
    if config.reward_risk < 1.0:
        raise ValueError("reward_risk_invalid")
    if config.setup_expiration_bars <= 0:
        raise ValueError("setup_expiration_invalid")
    if config.max_spread_points <= 0:
        raise ValueError("max_spread_invalid")
    if config.magic_number <= 0:
        raise ValueError("magic_number_invalid")


def validated_configuration(config: PullbackConfiguration) -> PullbackConfiguration:
    """Return the unchanged configuration only after all invariants pass."""

    validate_configuration(config)
    return config
