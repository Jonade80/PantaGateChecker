from __future__ import annotations

import time
from collections.abc import Sequence

import grpc
from ntt_proto.common.common_pb2 import VoidMessage
from ntt_proto.panta.panta_ecs_pb2 import GateState
from ntt_proto.panta.panta_ecs_pb2_grpc import (
    PantaEcsControlServiceVersion1Stub,
    PantaEcsMonitoringServiceVersion1Stub,
)

GATE_STATE_POLL_INTERVAL_SECONDS = 1.0


class PandoraGrpcClient:
    def __init__(self, endpoint: str, connection_timeout: float = 10.0) -> None:
        self.endpoint = endpoint
        self.connection_timeout = connection_timeout
        self.channel: grpc.Channel | None = None
        self.control: PantaEcsControlServiceVersion1Stub | None = None
        self.monitoring: PantaEcsMonitoringServiceVersion1Stub | None = None

    def connect(self) -> str:
        self.channel = grpc.insecure_channel(self.endpoint)
        try:
            grpc.channel_ready_future(self.channel).result(timeout=self.connection_timeout)
        except grpc.FutureTimeoutError as error:
            self.channel.close()
            raise ConnectionError(f"Could not connect to Pandora at {self.endpoint}") from error

        self.control = PantaEcsControlServiceVersion1Stub(self.channel)
        self.monitoring = PantaEcsMonitoringServiceVersion1Stub(self.channel)
        configuration = self.monitoring.Configuration(
            VoidMessage(), timeout=self.connection_timeout
        )
        return configuration.serial_number or "Unknown device"

    def close(self) -> None:
        if self.channel is not None:
            self.channel.close()

    def open_gate(self) -> None:
        self._control().OpenGate(VoidMessage(), timeout=10)

    def close_gate(self) -> None:
        self._control().CloseGate(VoidMessage(), timeout=10)

    def cancel_gate_operation(self) -> None:
        self._control().CancelGateOperation(VoidMessage(), timeout=10)

    def wait_for_gate_state(self, expected_states: Sequence[str], timeout: float) -> str:
        expected_values = {getattr(GateState, state) for state in expected_states}
        last_state = "no state received"
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            poll_started = time.monotonic()
            remaining = deadline - time.monotonic()
            call = self._monitoring().GateState(
                VoidMessage(), timeout=min(GATE_STATE_POLL_INTERVAL_SECONDS, remaining)
            )
            try:
                response = next(call)
                last_state = GateState.Name(response.gate_state)
                if response.gate_state in expected_values:
                    return last_state
            except grpc.RpcError as error:
                if error.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                    raise RuntimeError(
                        f"Pandora RPC failed: {error.code().name}: {error.details()}"
                    ) from error
            finally:
                call.cancel()

            remaining = deadline - time.monotonic()
            next_poll_delay = GATE_STATE_POLL_INTERVAL_SECONDS - (
                time.monotonic() - poll_started
            )
            if remaining > 0 and next_poll_delay > 0:
                time.sleep(min(next_poll_delay, remaining))

        expected = " or ".join(expected_states)
        raise TimeoutError(f"Timed out waiting for {expected}; last state was {last_state}")

    def __enter__(self) -> PandoraGrpcClient:
        self.connect()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _control(self) -> PantaEcsControlServiceVersion1Stub:
        if self.control is None:
            raise RuntimeError("Client is not connected")
        return self.control

    def _monitoring(self) -> PantaEcsMonitoringServiceVersion1Stub:
        if self.monitoring is None:
            raise RuntimeError("Client is not connected")
        return self.monitoring