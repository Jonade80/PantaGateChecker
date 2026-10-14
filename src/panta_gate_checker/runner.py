from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol, Sequence

class GateClient(Protocol):
    def open_gate(self) -> None: ...

    def close_gate(self) -> None: ...

    def cancel_gate_operation(self) -> None: ...

    def wait_for_gate_state(self, expected_states: Sequence[str], timeout: float) -> str: ...


@dataclass(frozen=True)
class CycleResult:
    number: int
    cancelled: bool
    passed: bool
    message: str
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True)
class TestSummary:
    device_name: str
    test_name: str
    requested_cycles: int
    results: tuple[CycleResult, ...]
    started_at: datetime
    finished_at: datetime
    error_message: str | None = None

    @property
    def passed(self) -> bool:
        return len(self.results) == self.requested_cycles and all(result.passed for result in self.results)


class GateTestRunner:
    def __init__(
        self,
        client: GateClient,
        cancellation_probability: float = 0.1,
        cancellation_delay_seconds: float = 0.1,
        operation_timeout_seconds: float = 120.0,
        random_source: random.Random | None = None,
    ) -> None:
        if not 0 <= cancellation_probability <= 1:
            raise ValueError("Cancellation probability must be between 0 and 1")

        self.client = client
        self.cancellation_probability = cancellation_probability
        self.cancellation_delay_seconds = cancellation_delay_seconds
        self.operation_timeout_seconds = operation_timeout_seconds
        self.random_source = random_source or random.Random()

    def run(
        self,
        device_name: str,
        test_name: str,
        cycles: int,
        on_result: Callable[[CycleResult], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> TestSummary:
        if cycles < 1:
            raise ValueError("At least one cycle is required")

        stop_event = stop_event or threading.Event()
        started_at = datetime.now()
        results: list[CycleResult] = []

        for cycle_number in range(1, cycles + 1):
            if stop_event.is_set():
                break

            result = self._run_cycle(cycle_number, stop_event)
            results.append(result)
            if on_result:
                on_result(result)
            if not result.passed:
                break

        return TestSummary(
            device_name=device_name,
            test_name=test_name,
            requested_cycles=cycles,
            results=tuple(results),
            started_at=started_at,
            finished_at=datetime.now(),
        )

    def _run_cycle(self, cycle_number: int, stop_event: threading.Event) -> CycleResult:
        started_at = datetime.now()
        should_cancel = self.random_source.random() < self.cancellation_probability

        try:
            self.client.open_gate()
            if should_cancel:
                self.client.wait_for_gate_state(["OPENING"], self.operation_timeout_seconds)
                if stop_event.wait(self.cancellation_delay_seconds):
                    raise InterruptedError("Test stopped by user")
                self.client.cancel_gate_operation()
                self.client.wait_for_gate_state(["CLOSED"], self.operation_timeout_seconds)
                message = "Open operation cancelled; gate recovered to CLOSED"
            else:
                self.client.wait_for_gate_state(["OPEN"], self.operation_timeout_seconds)
                self.client.close_gate()
                self.client.wait_for_gate_state(["CLOSED"], self.operation_timeout_seconds)
                message = "Gate opened and closed successfully"

            return CycleResult(
                number=cycle_number,
                cancelled=should_cancel,
                passed=True,
                message=message,
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as error:
            recovery_message = self._recover_to_closed()
            return CycleResult(
                number=cycle_number,
                cancelled=should_cancel,
                passed=False,
                message=f"{str(error) or type(error).__name__}. {recovery_message}",
                started_at=started_at,
                finished_at=datetime.now(),
            )

    def _recover_to_closed(self) -> str:
        try:
            state = self.client.wait_for_gate_state(
                ["OPEN", "CLOSED"], self.operation_timeout_seconds
            )
            if state == "OPEN":
                self.client.close_gate()
                self.client.wait_for_gate_state(["CLOSED"], self.operation_timeout_seconds)
            return "Gate recovered to CLOSED"
        except Exception as recovery_error:
            return f"Gate recovery failed: {str(recovery_error) or type(recovery_error).__name__}"