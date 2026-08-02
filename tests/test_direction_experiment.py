import pytest

from research.direction_experiment import DirectionExperiment, require_single_change


def test_baseline_allows_both_directions():
    gate = DirectionExperiment("both")
    assert gate.allows("long")
    assert gate.allows("short")


def test_long_only_blocks_only_short_entries():
    gate = DirectionExperiment("long_only")
    assert gate.allows("long")
    assert not gate.allows("short")


def test_invalid_direction_and_mode_fail_closed():
    with pytest.raises(ValueError, match="direction"):
        DirectionExperiment("both").allows("flat")
    with pytest.raises(ValueError, match="mode"):
        DirectionExperiment("invalid").allows("long")


def test_experiment_contract_accepts_only_both_vs_long_only():
    require_single_change(DirectionExperiment("both"), DirectionExperiment("long_only"))

    with pytest.raises(ValueError, match="baseline"):
        require_single_change(DirectionExperiment("short_only"), DirectionExperiment("long_only"))

    with pytest.raises(ValueError, match="candidate"):
        require_single_change(DirectionExperiment("both"), DirectionExperiment("short_only"))
