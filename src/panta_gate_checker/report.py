from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .runner import TestSummary


def create_pdf_report(summary: TestSummary, output_path: Path) -> Path:
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
    cancelled = sum(result.cancelled for result in summary.results)
    story = [
        Paragraph("Panta Gate Test Report", styles["Title"]),
        Spacer(1, 7 * mm),
        _summary_table(
            [
                ("Device", summary.device_name),
                ("Test", summary.test_name),
                ("Started", summary.started_at.strftime("%Y-%m-%d %H:%M:%S")),
                ("Finished", summary.finished_at.strftime("%Y-%m-%d %H:%M:%S")),
                ("Requested cycles", str(summary.requested_cycles)),
                ("Completed cycles", str(completed)),
                ("Cancelled open operations", str(cancelled)),
                ("Result", status),
            ]
        ),
        Spacer(1, 8 * mm),
        Paragraph("Cycle Results", styles["Heading2"]),
        Spacer(1, 3 * mm),
    ]

    rows = [["Cycle", "Operation", "Result", "Details"]]
    for result in summary.results:
        rows.append(
            [
                str(result.number),
                "Open cancelled" if result.cancelled else "Open / close",
                "PASS" if result.passed else "FAIL",
                Paragraph(result.message, styles["BodyText"]),
            ]
        )
    if not summary.results:
        rows.append(["-", "-", "FAIL", summary.error_message or "No cycles completed"])

    cycle_table = Table(rows, colWidths=[15 * mm, 35 * mm, 20 * mm, 84 * mm], repeatRows=1)
    cycle_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153F35")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BAC4BF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F4")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(cycle_table)
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