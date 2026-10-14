from __future__ import annotations

import random

from panta_gate_checker.runner import GateTestRunner


class FakeGateClient:
    def __init__(self, fail_on_state: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on_state = fail_on_state
        self.has_failed = False

    def open_gate(self) -> None:
        self.calls.append("open")

    def close_gate(self) -> None:
        self.calls.append("close")

    def cancel_gate_operation(self) -> None:
        self.calls.append("cancel")

    def wait_for_gate_state(self, expected_states, timeout: float) -> str:
        state = expected_states[0]
        self.calls.append(f"wait:{state}")
        if state == self.fail_on_state and not self.has_failed:
            self.has_failed = True
            raise TimeoutError(f"Timed out waiting for {state}")
        return state


def test_normal_cycle_opens_waits_and_closes() -> None:
    client = FakeGateClient()
    runner = GateTestRunner(client, cancellation_probability=0)

    summary = runner.run("PANTA-123", "Gate endurance", cycles=2)

    assert summary.passed
    assert client.calls == ["open", "wait:OPEN", "close", "wait:CLOSED"] * 2


def test_selected_open_cycle_is_cancelled_and_recovers_closed() -> None:
    client = FakeGateClient()
    runner = GateTestRunner(
        client,
        cancellation_probability=0.1,
        cancellation_delay_seconds=0,
        random_source=random.Random(31),
    )

    summary = runner.run("PANTA-123", "Gate endurance", cycles=1)

    assert summary.passed
    assert summary.results[0].cancelled
    assert client.calls == ["open", "wait:OPENING", "cancel", "wait:CLOSED"]


def test_failure_stops_following_cycles() -> None:
    client = FakeGateClient(fail_on_state="OPEN")
    runner = GateTestRunner(client, cancellation_probability=0)

    summary = runner.run("PANTA-123", "Gate endurance", cycles=3)

    assert not summary.passed
    assert len(summary.results) == 1
    assert summary.results[0].message == "Timed out waiting for OPEN. Gate recovered to CLOSED"
    assert client.calls == [
        "open",
        "wait:OPEN",
        "wait:OPEN",
        "close",
        "wait:CLOSED",
    ]
