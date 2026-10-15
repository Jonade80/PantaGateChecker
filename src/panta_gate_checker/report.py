from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import __version__
from .runner import TestSummary

BRAND_GREEN = colors.HexColor("#153F35")
PASSED_GREEN = colors.HexColor("#23864B")
FAILED_RED = colors.HexColor("#C83E3E")
LABEL_BACKGROUND = colors.HexColor("#EEF1EF")
BORDER_COLOR = colors.HexColor("#C9D0CC")
TEXT_COLOR = colors.HexColor("#25332E")


def create_pdf_report(summary: TestSummary, output_path: Path, operator_name: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now()
    styles = _report_styles()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=23 * mm,
        title=f"Panta Gate Checker Report - {summary.test_name} - {summary.device_name}",
        author="Panta Gate Checker",
    )

    result, result_color = _overall_result(summary)
    metrics = _summary_metrics(summary)
    information_rows = [
        ("Device Serial Number", summary.device_name),
        ("Test Name", summary.test_name),
        ("Operator", operator_name),
        ("Start Time", summary.started_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("End Time", summary.finished_at.strftime("%Y-%m-%d %H:%M:%S")),
    ]

    story = [
        Paragraph("Panta Gate Checker Report", styles["title"]),
        Paragraph("Automated Gate Stress Test", styles["subtitle"]),
        Spacer(1, 4 * mm),
        _overall_result_table(result, result_color, styles),
        Spacer(1, 4 * mm),
        Paragraph("Test Summary", styles["section"]),
        _metrics_table(metrics, styles),
        Spacer(1, 4 * mm),
        Paragraph("Test Information", styles["section"]),
        _information_table(information_rows, styles),
    ]

    failure_reasons = _failure_reasons(summary)
    if not summary.passed and failure_reasons:
        story.extend(
            [
                Spacer(1, 4 * mm),
                Paragraph("Failure Reason", styles["section"]),
                _failure_table(failure_reasons, styles),
            ]
        )

    def draw_footer(canvas: Canvas, _: SimpleDocTemplate) -> None:
        _draw_footer(canvas, generated_at, summary.device_name)

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output_path


def _report_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            textColor=BRAND_GREEN,
            spaceAfter=1.5 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base,
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#52625B"),
        ),
        "section": ParagraphStyle(
            "ReportSection",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=BRAND_GREEN,
            spaceAfter=1.5 * mm,
        ),
        "label": ParagraphStyle(
            "ReportLabel",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=TEXT_COLOR,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base,
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=TEXT_COLOR,
            alignment=TA_LEFT,
            wordWrap="LTR",
        ),
        "metric_label": ParagraphStyle(
            "ReportMetricLabel",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#52625B"),
            alignment=TA_LEFT,
        ),
        "metric_value": ParagraphStyle(
            "ReportMetricValue",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=BRAND_GREEN,
            alignment=TA_LEFT,
        ),
        "overall_label": ParagraphStyle(
            "ReportOverallLabel",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.white,
        ),
        "overall_result": ParagraphStyle(
            "ReportOverallResult",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            alignment=TA_LEFT,
        ),
    }


def _overall_result(summary: TestSummary) -> tuple[str, colors.Color]:
    if summary.passed:
        return "PASSED", PASSED_GREEN
    return "FAILED", FAILED_RED


def _summary_metrics(summary: TestSummary) -> tuple[tuple[str, str], ...]:
    completed = len(summary.results)
    passed = sum(result.passed for result in summary.results)
    failed = sum(not result.passed for result in summary.results)
    cancelled = sum(result.cancelled for result in summary.results)
    duration_seconds = max(0, int((summary.finished_at - summary.started_at).total_seconds()))
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
    return (
        ("Requested Cycles", str(summary.requested_cycles)),
        ("Completed Cycles", str(completed)),
        ("Passed Cycles", str(passed)),
        ("Failed Cycles", str(failed)),
        ("Cancelled Operations", str(cancelled)),
        ("Test Duration", duration),
    )


def _overall_result_table(
    result: str,
    result_color: colors.Color,
    styles: dict[str, ParagraphStyle],
) -> Table:
    status = Paragraph(result, ParagraphStyle("ResultValue", parent=styles["overall_result"], textColor=result_color))
    table = Table(
        [
            [
                Paragraph("OVERALL TEST RESULT", styles["overall_label"]),
                status,
            ]
        ],
        colWidths=[88 * mm, 88 * mm],
        rowHeights=[13 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), BRAND_GREEN),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F5F7F5")),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER_COLOR),
                ("LINEBEFORE", (1, 0), (1, 0), 0.6, BORDER_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _metrics_table(
    metrics: tuple[tuple[str, str], ...],
    styles: dict[str, ParagraphStyle],
) -> Table:
    cells = [
        [Paragraph(escape(label), styles["metric_label"]) for label, _ in metrics[:3]],
        [Paragraph(escape(value), styles["metric_value"]) for _, value in metrics[:3]],
        [Paragraph(escape(label), styles["metric_label"]) for label, _ in metrics[3:]],
        [Paragraph(escape(value), styles["metric_value"]) for _, value in metrics[3:]],
    ]
    table = Table(cells, colWidths=[176 * mm / 3] * 3, rowHeights=[8 * mm, 10 * mm, 8 * mm, 10 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LABEL_BACKGROUND),
                ("BACKGROUND", (0, 2), (-1, 2), LABEL_BACKGROUND),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BACKGROUND", (0, 3), (-1, 3), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, BORDER_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _information_table(
    rows: list[tuple[str, str]],
    styles: dict[str, ParagraphStyle],
) -> Table:
    data = [
        [
            Paragraph(escape(label), styles["label"]),
            Paragraph(escape(value), styles["body"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=[50 * mm, 126 * mm], repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LABEL_BACKGROUND),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, BORDER_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _failure_reasons(summary: TestSummary) -> tuple[str, ...]:
    reasons: list[str] = []
    if summary.error_message:
        reasons.append(summary.error_message)
    reasons.extend(
        f"Cycle {result.number}: {result.message}"
        for result in summary.results
        if not result.passed and result.message
    )
    return tuple(reasons)


def _failure_table(reasons: tuple[str, ...], styles: dict[str, ParagraphStyle]) -> Table:
    details = "<br/>".join(escape(reason).replace("\n", "<br/>") for reason in reasons)
    table = Table(
        [[Paragraph(details, styles["body"])]],
        colWidths=[176 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAF8F6")),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("LINEBEFORE", (0, 0), (0, 0), 2, FAILED_RED),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _draw_footer(canvas: Canvas, generated_at: datetime, device_name: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(17 * mm, 17 * mm, A4[0] - 17 * mm, 17 * mm)
    canvas.setFillColor(colors.HexColor("#52625B"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        17 * mm,
        12 * mm,
        f"Generated {generated_at:%Y-%m-%d %H:%M:%S}  |  Panta Gate Checker v{__version__}",
    )
    if device_name:
        canvas.drawRightString(A4[0] - 17 * mm, 7 * mm, f"Device Serial Number: {device_name}")
    canvas.restoreState()
