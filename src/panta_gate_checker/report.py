from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .runner import TestSummary


def create_pdf_report(summary: TestSummary, output_path: Path, operator_name: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{summary.test_name} - {summary.device_name}",
    )

    status = "PASSED" if summary.passed else "FAILED"
    completed = len(summary.results)
    passed = sum(result.passed for result in summary.results)
    failed = completed - passed
    cancelled = sum(result.cancelled for result in summary.results)
    summary_rows = [
        ("Device", summary.device_name),
        ("Test", summary.test_name),
        ("Operator", operator_name),
        ("Started", summary.started_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("Finished", summary.finished_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("Requested cycles", str(summary.requested_cycles)),
        ("Completed cycles", str(completed)),
        ("Passed cycles", str(passed)),
        ("Failed cycles", str(failed)),
        ("Cancelled open operations", str(cancelled)),
        ("Result", status),
    ]
    if summary.error_message:
        summary_rows.append(("Error", summary.error_message))

    story = [
        Paragraph("Panta Gate Test Report", styles["Title"]),
        Spacer(1, 7 * mm),
        _summary_table(summary_rows),
    ]

    document.build(story)
    return output_path


def _summary_table(rows: list[tuple[str, str]]) -> Table:
    table = Table(rows, colWidths=[52 * mm, 102 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E5ECE8")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BAC4BF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table