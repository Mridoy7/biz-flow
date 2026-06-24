from io import BytesIO
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def money(value):
    return f"${value:,.2f}"


def quantity(value):
    return f"{value:,.2f}"


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
        ("United Cards", record.united_card),
        ("Store Value Charge", record.store_value_charge),
        ("IOU", record.iou),
        ("Driveoffs", record.drive_offs),
        ("IOU Payment", record.iou_payment),
        ("Drive Off Payment", record.drive_off_payment),
        ("Cash", record.cash),
        ("Vault Drop / Cash Drop", record.vault_drop),
        ("Total sales", record.total_value),
        ("Terminal Total", record.total_sales_with_payments),
        ("Difference", record.difference),
        ("Total Fuel Sales", record.total_fuel_sales),
        ("Gross Shopsales", record.gross_shop_sales),
        ("Less: Surcharge", record.less_surcharge),
        ("Less: BBQ", Decimal("0.00")),
        ("Less: Ezypin", record.ezy_pin),
        ("Net Shop Sales", record.net_shop_sales),
    ]


def endofday_fuel_dip_rows(record):
    return [(f"Fuel Dip - {label}", value) for label, value in record.fuel_dip_items]


def styled_daysheet_table(rows, bold_labels=None, red_labels=None, pale_labels=None):
    table_rows = [[label, quantity(value) if label.startswith("Fuel Dip - ") else money(value) if isinstance(value, Decimal) else value] for label, value in rows]
    table = Table(table_rows, hAlign="LEFT", colWidths=[68 * mm, 42 * mm])
    row_lookup = {row[0]: index for index, row in enumerate(table_rows)}
    style_commands = [
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for label in bold_labels or []:
        row = row_lookup[label]
        style_commands.extend(
            [
                ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
                ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#f4f4f5")),
            ]
        )
    for label in pale_labels or []:
        row = row_lookup[label]
        style_commands.extend(
            [
                ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"),
                ("BACKGROUND", (0, row), (-1, row), colors.HexColor("#f8fafc")),
            ]
        )
    for label in red_labels or []:
        row = row_lookup[label]
        style_commands.append(("TEXTCOLOR", (0, row), (-1, row), colors.HexColor("#b91c1c")))
    table.setStyle(TableStyle(style_commands))
    return table


def image_upload_to_pdf(uploaded, title):
    buffer = BytesIO()
    page_width, page_height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(22 * mm, page_height - 22 * mm, title)
    image = ImageReader(uploaded)
    image_width, image_height = image.getSize()
    max_width = page_width - 44 * mm
    max_height = page_height - 52 * mm
    scale = min(max_width / image_width, max_height / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    x = (page_width - draw_width) / 2
    y = (page_height - draw_height) / 2 - 8 * mm
    pdf.drawImage(image, x, y, width=draw_width, height=draw_height, preserveAspectRatio=True, mask="auto")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def append_reader_pages(writer, reader):
    for page in reader.pages:
        writer.add_page(page)


def uploaded_daysheet_pdfs(record):
    upload_specs = [
        ("Master Sheet", record.master_sheet_file),
        ("End Of Days", record.end_of_days_file),
    ]
    for title, uploaded in upload_specs:
        if not uploaded:
            continue
        filename = uploaded.name.lower()
        try:
            with uploaded.open("rb") as file_obj:
                if filename.endswith(".pdf"):
                    yield PdfReader(file_obj)
                elif filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    yield PdfReader(image_upload_to_pdf(file_obj, title))
        except Exception:
            continue


def merged_endofday_pdf_bytes(record, base_pdf):
    writer = PdfWriter()
    append_reader_pages(writer, PdfReader(BytesIO(base_pdf)))
    for reader in uploaded_daysheet_pdfs(record):
        append_reader_pages(writer, reader)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


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

    summary_rows = ["Total sales", "Terminal Total", "Difference"]
    shop_rows = ["Total Fuel Sales", "Gross Shopsales", "Less: Surcharge", "Less: BBQ", "Less: Ezypin", "Net Shop Sales"]
    story.append(styled_daysheet_table(endofday_daysheet_rows(record), bold_labels=summary_rows, pale_labels=shop_rows, red_labels=["Net Shop Sales"]))

    if record.note:
        story.extend([Spacer(1, 10), Paragraph(f"Note: {record.note}", styles["Normal"])])

    story.extend(
        [
            PageBreak(),
            Paragraph("Fuel Dips", styles["Title"]),
            Paragraph(f"Date: {record.date:%d/%m/%Y}", styles["Normal"]),
            Spacer(1, 10),
            styled_daysheet_table(endofday_fuel_dip_rows(record), pale_labels=[label for label, value in endofday_fuel_dip_rows(record)]),
        ]
    )

    doc.build(story)
    pdf_bytes = merged_endofday_pdf_bytes(record, buffer.getvalue())
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    disposition = "attachment" if as_attachment else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="end-of-day-{record.date}.pdf"'
    return response


def report_pdf(filename, title, headers, rows, as_attachment=False):
    return pdf_response(
        filename,
        title,
        [("Report", [headers, *rows])],
        as_attachment=as_attachment,
        subtitle=f"Report Date: {timezone.localdate():%d/%m/%Y}",
    )
