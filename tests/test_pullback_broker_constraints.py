from research.pullback_broker_constraints import validate_margin, validate_stop_distances


def test_accepts_when_broker_has_no_minimum_stop_level() -> None:
    result = validate_stop_distances(
        entry=1.1000,
        stop=1.0985,
        target=1.10225,
        stops_level_points=0,
        point=0.00001,
    )
    assert result.accepted
    assert result.reason == "accepted"


def test_rejects_stop_inside_broker_minimum() -> None:
    result = validate_stop_distances(
        entry=1.1000,
        stop=1.0998,
        target=1.1020,
        stops_level_points=30,
        point=0.00001,
    )
    assert not result.accepted
    assert result.reason == "stop_too_close"


def test_rejects_target_inside_broker_minimum() -> None:
    result = validate_stop_distances(
        entry=1.1000,
        stop=1.0980,
        target=1.1002,
        stops_level_points=30,
        point=0.00001,
    )
    assert not result.accepted
    assert result.reason == "target_too_close"


def test_accepts_distances_equal_to_minimum() -> None:
    result = validate_stop_distances(
        entry=1.1000,
        stop=1.0997,
        target=1.1003,
        stops_level_points=30,
        point=0.00001,
    )
    assert result.accepted


def test_invalid_broker_metadata_fails_closed() -> None:
    result = validate_stop_distances(
        entry=1.1000,
        stop=1.0985,
        target=1.10225,
        stops_level_points=30,
        point=0.0,
    )
    assert not result.accepted
    assert result.reason == "invalid_stop_metadata"


def test_margin_accepts_equal_or_lower_requirement() -> None:
    assert validate_margin(required_margin=500.0, free_margin=500.0).accepted
    assert validate_margin(required_margin=400.0, free_margin=500.0).accepted


def test_margin_rejects_when_requirement_exceeds_free_margin() -> None:
    result = validate_margin(required_margin=501.0, free_margin=500.0)
    assert not result.accepted
    assert result.reason == "insufficient_margin"


def test_invalid_margin_data_fails_closed() -> None:
    result = validate_margin(required_margin=-1.0, free_margin=500.0)
    assert not result.accepted
    assert result.reason == "invalid_margin_data"
