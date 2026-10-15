from panta_gate_checker.app import _estimate_remaining_seconds, _format_countdown


def test_estimate_remaining_seconds_uses_elapsed_time_and_completed_cycles() -> None:
    assert _estimate_remaining_seconds(60.0, 2, 10) == 240


def test_estimate_remaining_seconds_waits_for_two_cycles() -> None:
    assert _estimate_remaining_seconds(30.0, 1, 10) is None


def test_estimate_remaining_seconds_never_goes_below_zero() -> None:
    assert _estimate_remaining_seconds(60.0, 10, 5) == 0


def test_format_countdown_always_uses_hours_minutes_and_seconds() -> None:
    assert _format_countdown(754) == "00:12:34"
    assert _format_countdown(-1) == "00:00:00"
