def test_application_modules_import() -> None:
    from pathlib import Path

    from panta_gate_checker.app import (
        DEFAULT_OUTPUT_DIRECTORY,
        DEFAULT_PANDORA_ENDPOINT,
        DEFAULT_TEST_NAME,
        GateCheckerApp,
        _format_duration,
    )
    from panta_gate_checker.grpc_client import PandoraGrpcClient
    from panta_gate_checker.report import create_pdf_report

    assert GateCheckerApp is not None
    assert PandoraGrpcClient is not None
    assert create_pdf_report is not None
    assert DEFAULT_TEST_NAME == "Gate Test"
    assert DEFAULT_OUTPUT_DIRECTORY == Path.home() / "Documents"
    assert DEFAULT_PANDORA_ENDPOINT == "172.16.4.1:2316"
    assert _format_duration(600) == "10:00"
    assert _format_duration(3723) == "1:02:03"