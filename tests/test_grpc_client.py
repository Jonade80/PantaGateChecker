from types import SimpleNamespace

from ntt_proto.panta.panta_ecs_pb2 import GateState

from panta_gate_checker.grpc_client import PandoraGrpcClient


class FakeGateStateCall:
    def __init__(self, state: int) -> None:
        self.response = SimpleNamespace(gate_state=state)
        self.cancelled = False

    def __iter__(self):
        return self

    def __next__(self):
        response = self.response
        self.response = None
        if response is None:
            raise StopIteration
        return response

    def cancel(self) -> None:
        self.cancelled = True


class FakeMonitoringService:
    def __init__(self, states: list[int]) -> None:
        self.states = iter(states)
        self.timeouts: list[float] = []
        self.calls: list[FakeGateStateCall] = []

    def GateState(self, _request, timeout: float) -> FakeGateStateCall:
        self.timeouts.append(timeout)
        call = FakeGateStateCall(next(self.states))
        self.calls.append(call)
        return call


def test_gate_state_is_polled_every_second_until_arrival(monkeypatch) -> None:
    monitoring = FakeMonitoringService([GateState.OPENING, GateState.OPEN])
    sleeps: list[float] = []
    monkeypatch.setattr("panta_gate_checker.grpc_client.time.sleep", sleeps.append)
    client = PandoraGrpcClient("172.16.4.1:2316")
    client.monitoring = monitoring

    state = client.wait_for_gate_state(["OPEN"], timeout=10)

    assert state == "OPEN"
    assert len(monitoring.calls) == 2
    assert all(call.cancelled for call in monitoring.calls)
    assert all(timeout <= 1 for timeout in monitoring.timeouts)
    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= 1