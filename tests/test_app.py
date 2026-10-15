from panta_gate_checker.app import _estimate_remaining_seconds


def test_estimate_remaining_seconds_uses_first_two_cycle_durations() -> None:
    assert _estimate_remaining_seconds([10.0, 20.0, 100.0], 3) == 45


def test_estimate_remaining_seconds_waits_for_two_cycles() -> None:
    assert _estimate_remaining_seconds([10.0], 3) is None
