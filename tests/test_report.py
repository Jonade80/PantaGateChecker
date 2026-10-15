from datetime import datetime

from reportlab.lib import colors

from panta_gate_checker.report import _summary_table, create_pdf_report
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

    output = create_pdf_report(summary, tmp_path / "report.pdf", "Alex Operator")

    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000


def test_passed_and_failed_summary_rows_use_green_and_red_text() -> None:
    table = _summary_table([("Passed", "2"), ("Failed", "1")])
    table.wrap(500, 700)

    assert table._cellStyles[0][0].color == colors.HexColor("#16803C")
    assert table._cellStyles[0][1].color == colors.HexColor("#16803C")
    assert table._cellStyles[1][0].color == colors.HexColor("#C62828")
    assert table._cellStyles[1][1].color == colors.HexColor("#C62828")