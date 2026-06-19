from io import BytesIO

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def money(value):
    return f"${value:,.2f}"


def pdf_response(filename, title, sections, as_attachment=False):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 8)]

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


def endofday_pdf(record):
    sections = [
        (
            "End of Day Summary",
            [
                ["Field", "Value"],
                ["Date", record.date],
                ["Entered By", record.entered_by],
                ["Total Sales", money(record.total_sales)],
                ["Gross Shop Sales", money(record.gross_shop_sales)],
                ["Total Value", money(record.total_value)],
                ["Difference", money(record.difference)],
                ["Net Shop Sales", money(record.net_shop_sales)],
                ["Created", record.created_at],
                ["Last Edited", record.updated_at],
            ],
        ),
        (
            "Payment Lines",
            [["Line", "Amount"], *[[label, money(amount)] for label, amount in record.line_items]],
        ),
        (
            "Notes",
            [
                ["Field", "Value"],
                ["Note", record.note or "-"],
            ],
        ),
    ]
    return pdf_response(f"end-of-day-{record.date}.pdf", f"End of Day {record.date}", sections)


def report_pdf(filename, title, headers, rows):
    return pdf_response(filename, title, [("Report", [headers, *rows])])
