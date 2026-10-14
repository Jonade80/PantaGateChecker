from datetime import datetime

from panta_gate_checker.report import create_pdf_report
from panta_gate_checker.runner import CycleResult, TestSummary as Summary


def test_create_pdf_report(tmp_path) -> None:
    now = datetime(2026, 10, 14, 10, 30)
    summary = Summary(
        device_name="PANTA-123",
        test_name="Gate endurance",
        requested_cycles=1,
        results=(CycleResult(1, False, True, "Gate opened and closed successfully", now, now),),
        started_at=now,
        finished_at=now,
    )

    output = create_pdf_report(summary, tmp_path / "report.pdf")

    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000