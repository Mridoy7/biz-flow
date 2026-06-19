from io import BytesIO
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def money(value):
    return f"${value:,.2f}"


def pdf_response(filename, title, sections, as_attachment=False, subtitle=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 8)]
    if subtitle:
        story.extend([Paragraph(subtitle, styles["Normal"]), Spacer(1, 8)])

    for heading, rows in sections:
        story.append(Paragraph(heading, styles["Heading2"]))
        table = Table(rows, hAlign="LEFT", colWidths=[62 * mm, 102 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7eff8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 12))

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    disposition = "attachment" if as_attachment else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


def invoice_pdf(invoice):
    rows = [
        ["Field", "Value"],
        ["Supplier", invoice.supplier.name],
        ["Invoice Date", invoice.invoice_date],
        ["Invoice Number", invoice.invoice_number],
        ["Entered By", invoice.entered_by],
        ["Amount", money(invoice.invoice_amount) if invoice.invoice_amount is not None else "Not entered"],
        ["Notes", invoice.notes or "-"],
        ["Uploaded File", invoice.invoice_file.url if invoice.invoice_file else "-"],
        ["Created", invoice.created_at],
        ["Last Edited", invoice.updated_at],
    ]
    return pdf_response(f"invoice-{invoice.pk}.pdf", f"Invoice {invoice.invoice_number}", [("Invoice Details", rows)])


def endofday_daysheet_rows(record):
    return [
        ("Date", record.date.strftime("%d/%m/%Y")),
        ("Uber Eats", record.uber_eats),
        ("Door Dash", record.doordash),
        ("Motorpass", record.motorpass),
        ("Motorcharge", record.motorcharge),
        ("Fleet", record.fleet_card),
        ("Eftpos", record.eftpos),
        ("Amex", record.amex_card),
        ("Diners", record.diners_card),
        ("United Cards", record.adjusted_united_card),
        ("IOU", record.iou),
        ("Driveoffs", record.drive_offs),
        ("Cash", record.cash),
        ("Vault Drop", record.vault_drop),
        ("Total", record.total_value),
        ("Total sales", record.total_sales),
        ("Difference", record.difference),
        ("Gross Shopsales", record.gross_shop_sales),
        ("Less: Surcharge", record.less_surcharge),
        ("Less: BBQ", Decimal("0.00")),
        ("Less: Ezypin", record.ezy_pin),
        ("Net Shop Sales", record.net_shop_sales),
    ]


def endofday_pdf(record, as_attachment=False):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    site_name = record.site_name.strip() if record.site_name else ""
    title = f"Daysheet {site_name}" if site_name else "Daysheet"
    story = [
        Paragraph(title, styles["Title"]),
        Paragraph(f"Entered by: {record.entered_by}", styles["Normal"]),
        Spacer(1, 10),
    ]

    table_rows = []
    for label, value in endofday_daysheet_rows(record):
        table_rows.append([label, money(value) if isinstance(value, Decimal) else value])
    table = Table(table_rows, hAlign="LEFT", colWidths=[68 * mm, 42 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("FONTNAME", (0, 14), (-1, 16), "Helvetica-Bold"),
                ("FONTNAME", (0, 17), (-1, 21), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 21), (-1, 21), colors.HexColor("#b91c1c")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 14), (-1, 16), colors.HexColor("#f4f4f5")),
                ("BACKGROUND", (0, 17), (-1, 21), colors.HexColor("#f8fafc")),
            ]
        )
    )
    story.append(table)

    if record.note:
        story.extend([Spacer(1, 10), Paragraph(f"Note: {record.note}", styles["Normal"])])

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    disposition = "attachment" if as_attachment else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="end-of-day-{record.date}.pdf"'
    return response


def report_pdf(filename, title, headers, rows):
    return pdf_response(
        filename,
        title,
        [("Report", [headers, *rows])],
        subtitle=f"Report Date: {timezone.localdate():%d/%m/%Y}",
    )
