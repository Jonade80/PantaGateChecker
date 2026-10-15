from datetime import datetime, timedelta

from reportlab.lib import colors

from panta_gate_checker.report import (
    FAILED_RED,
    PASSED_GREEN,
    _failure_reasons,
    _metrics_table,
    _overall_result,
    _overall_result_table,
    _report_styles,
    _summary_metrics,
    create_pdf_report,
)
from panta_gate_checker.runner import CycleResult, TestSummary as Summary


def _cycle(number: int, passed: bool, message: str, cancelled: bool = False) -> CycleResult:
    started = datetime(2026, 10, 14, 10, 30) + timedelta(minutes=number - 1)
    return CycleResult(
        number=number,
        cancelled=cancelled,
        passed=passed,
        message=message,
        started_at=started,
        finished_at=started + timedelta(seconds=30),
    )


def test_create_pdf_report_for_passed_test(tmp_path) -> None:
    now = datetime(2026, 10, 14, 10, 30)
    summary = Summary(
        device_name="PANTA-123",
        test_name="Gate endurance",
        requested_cycles=1,
        results=(_cycle(1, True, "Gate opened and closed successfully", cancelled=True),),
        started_at=now,
        finished_at=now + timedelta(seconds=30),
    )

    output = create_pdf_report(summary, tmp_path / "passed-report.pdf", "Alex Operator")

    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000
    assert _overall_result(summary) == ("PASSED", PASSED_GREEN)
    assert _summary_metrics(summary) == (
        ("Requested Cycles", "1"),
        ("Completed Cycles", "1"),
        ("Passed Cycles", "1"),
        ("Failed Cycles", "0"),
        ("Cancelled Operations", "1"),
        ("Test Duration", "00:30"),
    )
    status_table = _overall_result_table(*_overall_result(summary), _report_styles())
    assert status_table._cellvalues[0][1].style.textColor == colors.HexColor("#23864B")


def test_failed_test_report_shows_actual_cycle_failure(tmp_path) -> None:
    now = datetime(2026, 10, 14, 10, 30)
    summary = Summary(
        device_name="PANTA-456",
        test_name="Gate endurance",
        requested_cycles=3,
        results=(
            _cycle(1, True, "Gate opened and closed successfully"),
            _cycle(2, False, "Timed out waiting for OPEN. Gate recovered to CLOSED"),
        ),
        started_at=now,
        finished_at=now + timedelta(minutes=1, seconds=30),
    )

    output = create_pdf_report(summary, tmp_path / "failed-report.pdf", "Alex Operator")

    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 1000
    assert _overall_result(summary) == ("FAILED", FAILED_RED)
    assert _summary_metrics(summary) == (
        ("Requested Cycles", "3"),
        ("Completed Cycles", "2"),
        ("Passed Cycles", "1"),
        ("Failed Cycles", "1"),
        ("Cancelled Operations", "0"),
        ("Test Duration", "01:30"),
    )
    assert _failure_reasons(summary) == ("Cycle 2: Timed out waiting for OPEN. Gate recovered to CLOSED",)
    status_table = _overall_result_table(*_overall_result(summary), _report_styles())
    assert status_table._cellvalues[0][1].style.textColor == colors.HexColor("#C83E3E")


def test_incomplete_test_result_is_not_inferred_from_cycle_counts() -> None:
    now = datetime(2026, 10, 14, 10, 30)
    summary = Summary(
        device_name="PANTA-789",
        test_name="Gate endurance",
        requested_cycles=3,
        results=(_cycle(1, True, "Gate opened and closed successfully"),),
        started_at=now,
        finished_at=now + timedelta(seconds=30),
    )

    assert _overall_result(summary) == ("FAILED", FAILED_RED)
    assert _summary_metrics(summary)[1:4] == (
        ("Completed Cycles", "1"),
        ("Passed Cycles", "1"),
        ("Failed Cycles", "0"),
    )
    assert _failure_reasons(summary) == ()


def test_summary_error_is_reported_as_failure_reason() -> None:
    now = datetime(2026, 10, 14, 10, 30)
    summary = Summary(
        device_name="PANTA-123",
        test_name="Gate endurance",
        requested_cycles=1,
        results=(),
        started_at=now,
        finished_at=now,
        error_message="Connection refused",
    )

    assert _failure_reasons(summary) == ("Connection refused",)


def test_metrics_table_uses_six_equal_columns() -> None:
    table = _metrics_table(
        (
            ("Requested Cycles", "3"),
            ("Completed Cycles", "2"),
            ("Passed Cycles", "1"),
            ("Failed Cycles", "1"),
            ("Cancelled Operations", "0"),
            ("Test Duration", "01:30"),
        ),
        _report_styles(),
    )
    table.wrap(500, 700)

    assert len(table._cellvalues[0]) == 3
    assert table._colWidths == [176 * 72 / 25.4 / 3] * 3
