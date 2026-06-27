from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from .forms import EndOfDayForm, InvoiceForm, endofday_date_bounds
from .models import AccountRole, EndOfDay, Invoice, InvoiceAttachment, StoreSite, Supplier
from .pdf import endofday_daysheet_rows, endofday_fuel_dip_rows


def sample_pdf_bytes(text="Uploaded page"):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class HomeRedirectTests(TestCase):
    def test_signed_out_home_redirects_to_login(self):
        response = self.client.get("/")

        self.assertRedirects(response, "/accounts/login/")


class EndOfDayCalculationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")

    def make_record(self, **overrides):
        data = {
            "user": self.user,
            "date": date(2026, 6, 20),
            "entered_by": "Ridoy",
            "uber_eats": 10,
            "doordash": 10,
            "eftpos": 100,
            "amex_card": 10,
            "motorpass": 10,
            "motorcharge": 0,
            "fleet_card": 10,
            "diners_card": 0,
            "united_card": 100,
            "store_value_charge": 10,
            "iou": 5,
            "drive_offs": 10,
            "cash": 100,
            "vault_drop": 20,
            "total_sales": 370,
            "total_fuel_sales": 0,
            "gross_shop_sales": 370,
            "ezy_pin": 20,
            "less_surcharge": 5,
        }
        data.update(overrides)
        return EndOfDay(**data)

    def test_spec_example_calculates_correctly(self):
        record = self.make_record(note="Explained")
        record.full_clean()

        self.assertEqual(record.adjusted_united_card, Decimal("95"))
        self.assertEqual(record.total_value, Decimal("380"))
        self.assertEqual(record.difference, Decimal("10"))
        self.assertEqual(record.net_shop_sales, Decimal("345"))

    def test_iou_and_drive_off_payments_add_to_total_sales_reconciliation(self):
        record = self.make_record(iou_payment=7, drive_off_payment=3, note="Explained")
        record.full_clean()

        self.assertEqual(record.total_value, Decimal("390"))
        self.assertEqual(record.total_sales_with_payments, Decimal("380"))
        self.assertEqual(record.difference, Decimal("10"))

    def test_gross_shop_sales_uses_total_sales_less_fuel_sales(self):
        record = self.make_record(total_sales=500, total_fuel_sales=130, ezy_pin=20, less_surcharge=5, note="Explained")
        record.full_clean()

        self.assertEqual(record.difference, Decimal("-120"))
        self.assertEqual(record.gross_shop_sales, Decimal("370"))
        self.assertEqual(record.net_shop_sales, Decimal("345"))

    def test_note_required_when_difference_over_five(self):
        record = self.make_record(note="")

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_note_optional_when_difference_within_five(self):
        record = self.make_record(total_sales=378, note="")
        record.full_clean()

        self.assertEqual(record.difference, Decimal("2"))


class SameDayFormValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.supplier = Supplier.objects.create(user=self.user, name="Fuel Supplier")

    def endofday_required_data(self, **overrides):
        data = {
            "date": timezone.localdate().isoformat(),
            "site_name": "Holtze",
            "entered_by": "Ridoy",
            "total_sales": "0",
            "total_fuel_sales": "0",
            "gross_shop_sales": "0",
            "ezy_pin": "0",
            "less_surcharge": "0",
            "fuel_dip_1_name": "E85 tank 1",
            "fuel_dip_1_value": "0",
            "fuel_dip_2_name": "Unleaded 91 tank 1",
            "fuel_dip_2_value": "0",
            "fuel_dip_3_name": "Unleaded 95 tank 1",
            "fuel_dip_3_value": "0",
            "fuel_dip_4_name": "Unleaded 98 tank 1",
            "fuel_dip_4_value": "0",
            "fuel_dip_5_name": "Diesel tank 1",
            "fuel_dip_5_value": "0",
            "fuel_dip_6_name": "Diesel tank 2",
            "fuel_dip_6_value": "0",
        }
        data.update(overrides)
        return data

    def endofday_required_files(self):
        return {
            "master_sheet_file": SimpleUploadedFile("master-sheet.pdf", b"%PDF-1.4\nmaster", content_type="application/pdf"),
            "end_of_days_file": SimpleUploadedFile("end-of-days.pdf", b"%PDF-1.4\ndays", content_type="application/pdf"),
        }

    def test_invoice_form_rejects_previous_day(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        upload = SimpleUploadedFile("invoice.pdf", b"invoice", content_type="application/pdf")
        form = InvoiceForm(
            data={
                "supplier": self.supplier.pk,
                "invoice_date": yesterday.isoformat(),
                "invoice_number": "INV-OLD",
                "entered_by": "Ridoy",
            },
            files={"invoice_pages": upload},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Invoice date must be today's date.", form.errors["invoice_date"])

    def test_invoice_form_rejects_duplicate_supplier_invoice_number(self):
        today = timezone.localdate()
        upload = SimpleUploadedFile("invoice.pdf", b"invoice", content_type="application/pdf")
        Invoice.objects.create(
            user=self.user,
            supplier=self.supplier,
            invoice_date=today,
            invoice_number="INV-1",
            invoice_file=upload,
            entered_by="Ridoy",
        )
        duplicate_upload = SimpleUploadedFile("invoice2.pdf", b"invoice", content_type="application/pdf")
        form = InvoiceForm(
            data={
                "supplier": self.supplier.pk,
                "invoice_date": today.isoformat(),
                "invoice_number": "INV-1",
                "entered_by": "Ridoy",
            },
            files={"invoice_pages": duplicate_upload},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("This invoice number already exists for this supplier.", form.errors["invoice_number"])

    def test_endofday_form_rejects_previous_day(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        after_cutoff = timezone.make_aware(datetime.combine(today, time(5, 0)))
        with patch("gst_app.forms.timezone.now", return_value=after_cutoff):
            form = EndOfDayForm(
                data=self.endofday_required_data(date=yesterday.isoformat()),
                files=self.endofday_required_files(),
                user=self.user,
            )
            self.assertFalse(form.is_valid())
            self.assertIn("End of Day date must be today, or yesterday before 4am.", form.errors["date"])

    def test_endofday_draft_allows_incomplete_day_sheet(self):
        form = EndOfDayForm(
            data={"date": timezone.localdate().isoformat()},
            user=self.user,
            submission_mode=False,
        )

        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(TIME_ZONE="Australia/Darwin")
    def test_endofday_date_allows_yesterday_before_4am(self):
        at_one_am = timezone.make_aware(datetime(2026, 6, 27, 1, 0))
        at_four_am = timezone.make_aware(datetime(2026, 6, 27, 4, 0))

        with patch("gst_app.forms.timezone.now", return_value=at_one_am):
            self.assertEqual(endofday_date_bounds(), (date(2026, 6, 26), date(2026, 6, 27)))
        with patch("gst_app.forms.timezone.now", return_value=at_four_am):
            self.assertEqual(endofday_date_bounds(), (date(2026, 6, 27), date(2026, 6, 27)))

    def test_endofday_form_accepts_site_name(self):
        form = EndOfDayForm(
            data=self.endofday_required_data(),
            files=self.endofday_required_files(),
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["site_name"], "Holtze")

    def test_endofday_form_prioritizes_common_payment_fields(self):
        form = EndOfDayForm(user=self.user)
        field_names = list(form.fields)

        self.assertEqual(
            field_names[3:12],
            ["cash", "eftpos", "amex_card", "fleet_card", "motorpass", "motorcharge", "united_card", "iou", "drive_offs"],
        )
        self.assertEqual(field_names[12], "vault_drop")
        self.assertEqual(form.fields["vault_drop"].label, "Vault Drop / Cash Drop")

    def test_endofday_form_includes_fuel_dip_fields(self):
        form = EndOfDayForm(user=self.user)

        self.assertEqual(form.fields["total_sales"].label, "Terminal Total")
        self.assertEqual(form.fields["fuel_dip_1_name"].label, "Fuel Tank 1")
        self.assertEqual(form.fields["fuel_dip_1_name"].widget.attrs["placeholder"], "Fuel grade")
        self.assertEqual(form.fields["fuel_dip_1_value"].label, "Tank 1 dip value")
        self.assertEqual(form.fields["fuel_dip_6_name"].label, "Fuel Tank 6")
        self.assertEqual(form.fields["fuel_dip_6_value"].label, "Tank 6 dip value")
        self.assertTrue(form.fields["fuel_dip_1_name"].required)
        self.assertTrue(form.fields["fuel_dip_6_value"].required)
        self.assertTrue(form.fields["master_sheet_file"].required)
        self.assertTrue(form.fields["end_of_days_file"].required)

    def test_endofday_form_requires_fuel_dips_and_day_sheet_uploads(self):
        data = self.endofday_required_data()
        data.pop("fuel_dip_1_name")
        form = EndOfDayForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("fuel_dip_1_name", form.errors)
        self.assertIn("master_sheet_file", form.errors)
        self.assertIn("end_of_days_file", form.errors)


class InvoiceFileDownloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.supplier = Supplier.objects.create(user=self.user, name="Fuel Supplier")
        self.temp_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)

    def test_invoice_file_download_is_available_to_owner(self):
        upload = SimpleUploadedFile("invoice.pdf", b"invoice", content_type="application/pdf")
        invoice = Invoice.objects.create(
            user=self.user,
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            invoice_number="INV-DOWNLOAD",
            invoice_file=upload,
            entered_by="Ridoy",
        )
        self.client.login(username="owner", password="test-pass")

        response = self.client.get(f"/invoices/{invoice.pk}/file/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_invoice_file_preview_is_inline(self):
        upload = SimpleUploadedFile("invoice.pdf", b"invoice", content_type="application/pdf")
        invoice = Invoice.objects.create(
            user=self.user,
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            invoice_number="INV-PREVIEW",
            invoice_file=upload,
            entered_by="Ridoy",
        )
        self.client.login(username="owner", password="test-pass")

        response = self.client.get(f"/invoices/{invoice.pk}/file/preview/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")

    def test_invoice_list_file_action_previews_before_download(self):
        upload = SimpleUploadedFile("invoice.pdf", b"invoice", content_type="application/pdf")
        Invoice.objects.create(
            user=self.user,
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            invoice_number="INV-PREVIEW-BUTTON",
            invoice_file=upload,
            entered_by="Ridoy",
        )
        self.client.login(username="owner", password="test-pass")

        response = self.client.get("/invoices/")

        self.assertContains(response, "invoice-preview-button")
        self.assertContains(response, "Invoice PDF")
        self.assertContains(response, f'href="/invoices/{Invoice.objects.get(invoice_number="INV-PREVIEW-BUTTON").pk}/file/preview/"')
        self.assertContains(response, "data-preview-url=")
        self.assertContains(response, "data-download-url=")
        self.assertContains(response, "invoiceExportPreviewModal")
        self.assertContains(response, "data-export-label=\"Invoice PDF Report\"")
        self.assertContains(response, "data-export-label=\"Invoice Excel Report\"")
        self.assertContains(response, "data-export-label=\"Invoice CSV Report\"")

    def test_non_previewable_invoice_file_does_not_load_in_preview_frame(self):
        upload = SimpleUploadedFile(
            "invoice.docx",
            b"invoice",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        Invoice.objects.create(
            user=self.user,
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            invoice_number="INV-DOCX",
            invoice_file=upload,
            entered_by="Ridoy",
        )
        self.client.login(username="owner", password="test-pass")

        response = self.client.get("/invoices/")

        self.assertContains(response, 'data-previewable="0"')
        self.assertContains(response, "Preview not available for this file type.")

    def test_invoice_form_accepts_multiple_pages_and_serves_one_pdf(self):
        self.client.login(username="owner", password="test-pass")
        with override_settings(MEDIA_ROOT=self.temp_media.name):
            response = self.client.post(
                "/invoices/add/",
                {
                    "supplier": self.supplier.pk,
                    "invoice_date": timezone.localdate().isoformat(),
                    "invoice_number": "INV-MULTI",
                    "entered_by": "Ridoy",
                    "invoice_pages": [
                        SimpleUploadedFile("main.pdf", sample_pdf_bytes("Page 1"), content_type="application/pdf"),
                        SimpleUploadedFile("page-2.pdf", sample_pdf_bytes("Page 2"), content_type="application/pdf"),
                        SimpleUploadedFile("page-3.pdf", sample_pdf_bytes("Page 3"), content_type="application/pdf"),
                    ],
                },
            )

            self.assertEqual(response.status_code, 302)
            invoice = Invoice.objects.get(invoice_number="INV-MULTI")
            self.assertEqual(invoice.attachments.count(), 2)
            detail_response = self.client.get(invoice.get_absolute_url())
            preview_response = self.client.get(f"/invoices/{invoice.pk}/file/preview/")

        merged_pdf = PdfReader(BytesIO(preview_response.content))
        self.assertContains(detail_response, "Preview combined invoice")
        self.assertContains(detail_response, "Page 1")
        self.assertContains(detail_response, "Page 2")
        self.assertContains(detail_response, "Page 3")
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(len(merged_pdf.pages), 3)
        self.assertIn("inline", preview_response["Content-Disposition"])
        self.assertEqual(preview_response["X-Frame-Options"], "SAMEORIGIN")

    def test_invoice_form_shows_polished_multi_upload_controls(self):
        self.client.login(username="owner", password="test-pass")

        response = self.client.get("/invoices/add/")

        self.assertContains(response, "Upload Invoice", count=2)
        self.assertContains(response, "No invoice uploaded yet")
        self.assertNotContains(response, "Select all pages together")
        self.assertNotContains(response, "Select one or more pages")
        self.assertContains(response, "invoice-upload-card")
        self.assertContains(response, "data-upload-list")
        self.assertContains(response, "selectedFiles = selectedFiles.concat")
        self.assertContains(response, "Page ${index + 1}: ${file.name}")
        self.assertContains(response, "Remove")

    def test_cash_purchase_form_accepts_amount_and_multiple_pages(self):
        self.client.login(username="owner", password="test-pass")
        with override_settings(MEDIA_ROOT=self.temp_media.name):
            response = self.client.post(
                "/invoices/cash-purchase/add/",
                {
                    "purchase_from": "Local Hardware",
                    "invoice_date": timezone.localdate().isoformat(),
                    "invoice_number": "CASH-1",
                    "entered_by": "Ridoy",
                    "invoice_amount": "42.50",
                    "invoice_pages": [
                        SimpleUploadedFile("cash-page-1.pdf", sample_pdf_bytes("Cash page 1"), content_type="application/pdf"),
                        SimpleUploadedFile("cash-page-2.pdf", sample_pdf_bytes("Cash page 2"), content_type="application/pdf"),
                    ],
                },
            )

            self.assertEqual(response.status_code, 302)
            invoice = Invoice.objects.get(invoice_number="CASH-1")
            detail_response = self.client.get(invoice.get_absolute_url())
            preview_response = self.client.get(f"/invoices/{invoice.pk}/file/preview/")

        merged_pdf = PdfReader(BytesIO(preview_response.content))
        self.assertTrue(invoice.is_cash_purchase)
        self.assertIsNone(invoice.supplier)
        self.assertEqual(invoice.purchase_from, "Local Hardware")
        self.assertEqual(invoice.invoice_amount, Decimal("42.50"))
        self.assertEqual(invoice.attachments.count(), 1)
        self.assertContains(detail_response, "Cash Purchase")
        self.assertContains(detail_response, "Local Hardware")
        self.assertEqual(len(merged_pdf.pages), 2)

    def test_invoice_edit_upload_adds_pages_without_deleting_existing_pages(self):
        self.client.login(username="owner", password="test-pass")
        with override_settings(MEDIA_ROOT=self.temp_media.name):
            invoice = Invoice.objects.create(
                user=self.user,
                supplier=self.supplier,
                invoice_date=timezone.localdate(),
                invoice_number="INV-ADD-PAGES",
                invoice_file=SimpleUploadedFile("page-1.pdf", sample_pdf_bytes("Page 1"), content_type="application/pdf"),
                entered_by="Ridoy",
            )

            edit_response = self.client.get(f"/invoices/{invoice.pk}/edit/")
            response = self.client.post(
                f"/invoices/{invoice.pk}/edit/",
                {
                    "supplier": self.supplier.pk,
                    "invoice_date": timezone.localdate().isoformat(),
                    "invoice_number": "INV-ADD-PAGES",
                    "entered_by": "Ridoy",
                    "invoice_pages": [
                        SimpleUploadedFile("page-2.pdf", sample_pdf_bytes("Page 2"), content_type="application/pdf"),
                        SimpleUploadedFile("page-3.pdf", sample_pdf_bytes("Page 3"), content_type="application/pdf"),
                    ],
                },
            )
            invoice.refresh_from_db()
            preview_response = self.client.get(f"/invoices/{invoice.pk}/file/preview/")

        merged_pdf = PdfReader(BytesIO(preview_response.content))
        self.assertContains(edit_response, "Upload Invoice")
        self.assertEqual(response.status_code, 302)
        self.assertIn("page-1", invoice.invoice_file.name)
        self.assertEqual(invoice.attachments.count(), 2)
        self.assertEqual(len(merged_pdf.pages), 3)

    def test_invoice_edit_can_replace_and_delete_extra_files(self):
        self.client.login(username="owner", password="test-pass")
        with override_settings(MEDIA_ROOT=self.temp_media.name):
            invoice = Invoice.objects.create(
                user=self.user,
                supplier=self.supplier,
                invoice_date=timezone.localdate(),
                invoice_number="INV-EDIT-FILES",
                invoice_file=SimpleUploadedFile("main.pdf", b"%PDF-1.4\nmain", content_type="application/pdf"),
                entered_by="Ridoy",
            )
            replace_attachment = InvoiceAttachment.objects.create(
                invoice=invoice,
                file=SimpleUploadedFile("old-page.jpg", b"old", content_type="image/jpeg"),
                uploaded_by=self.user,
            )
            delete_attachment = InvoiceAttachment.objects.create(
                invoice=invoice,
                file=SimpleUploadedFile("delete-page.jpg", b"delete", content_type="image/jpeg"),
                uploaded_by=self.user,
            )

            edit_response = self.client.get(f"/invoices/{invoice.pk}/edit/")

            response = self.client.post(
                f"/invoices/{invoice.pk}/edit/",
                {
                    "supplier": self.supplier.pk,
                    "invoice_date": timezone.localdate().isoformat(),
                    "invoice_number": "INV-EDIT-FILES",
                    "entered_by": "Ridoy",
                    f"replace_attachment_{replace_attachment.pk}": SimpleUploadedFile(
                        "new-page.jpg",
                        b"new",
                        content_type="image/jpeg",
                    ),
                    "delete_attachments": [str(delete_attachment.pk)],
                },
            )

            self.assertEqual(response.status_code, 302)
            invoice.refresh_from_db()
            replace_attachment.refresh_from_db()

        self.assertContains(edit_response, "Current invoice pages")
        self.assertContains(edit_response, "Preview combined PDF")
        self.assertContains(edit_response, "Change file")
        self.assertContains(edit_response, "Delete this file")
        self.assertEqual(invoice.attachments.count(), 1)
        self.assertIn("new-page", replace_attachment.filename)
        self.assertFalse(InvoiceAttachment.objects.filter(pk=delete_attachment.pk).exists())


class EndOfDayFileUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.temp_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        self.client.login(username="owner", password="test-pass")

    def test_endofday_form_can_upload_master_sheet_and_end_of_days_files(self):
        master_sheet = SimpleUploadedFile("master-sheet.pdf", b"%PDF-1.4\nmaster", content_type="application/pdf")
        end_of_days = SimpleUploadedFile(
            "end-of-days.docx",
            b"end-of-days",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        with override_settings(MEDIA_ROOT=self.temp_media.name):
            response = self.client.post(
                "/end-of-day/add/",
                {
                    "date": timezone.localdate().isoformat(),
                    "site_name": "Holtze",
                    "entered_by": "Ridoy",
                    "total_sales": "0",
                    "total_fuel_sales": "0",
                    "gross_shop_sales": "0",
                    "ezy_pin": "0",
                    "less_surcharge": "0",
                    "fuel_dip_1_name": "E85 tank 1",
                    "fuel_dip_1_value": "0",
                    "fuel_dip_2_name": "Unleaded 91 tank 1",
                    "fuel_dip_2_value": "0",
                    "fuel_dip_3_name": "Unleaded 95 tank 1",
                    "fuel_dip_3_value": "0",
                    "fuel_dip_4_name": "Unleaded 98 tank 1",
                    "fuel_dip_4_value": "0",
                    "fuel_dip_5_name": "Diesel tank 1",
                    "fuel_dip_5_value": "0",
                    "fuel_dip_6_name": "Diesel tank 2",
                    "fuel_dip_6_value": "0",
                    "master_sheet_file": master_sheet,
                    "end_of_days_file": end_of_days,
                },
            )

            self.assertEqual(response.status_code, 302)
            record = EndOfDay.objects.get(user=self.user, date=timezone.localdate())
            self.assertTrue(record.master_sheet_file.name.endswith(".pdf"))
            self.assertTrue(record.end_of_days_file.name.endswith(".docx"))

    def test_endofday_draft_saves_delivery_docket_without_final_documents(self):
        delivery_docket = SimpleUploadedFile("delivery-docket.pdf", b"%PDF-1.4\ndocket", content_type="application/pdf")

        with override_settings(MEDIA_ROOT=self.temp_media.name):
            response = self.client.post(
                "/end-of-day/add/",
                {
                    "date": timezone.localdate().isoformat(),
                    "action": "save_draft",
                    "delivery_docket_file": delivery_docket,
                },
            )

            self.assertEqual(response.status_code, 302)
            record = EndOfDay.objects.get(user=self.user, date=timezone.localdate())
            self.assertFalse(record.is_submitted)
            self.assertTrue(record.delivery_docket_file.name.endswith(".pdf"))

    def test_endofday_detail_previews_uploaded_files_before_download(self):
        with override_settings(MEDIA_ROOT=self.temp_media.name):
            record = EndOfDay.objects.create(
                user=self.user,
                date=timezone.localdate(),
                entered_by="Ridoy",
                total_sales=0,
                ezy_pin=0,
                less_surcharge=0,
                master_sheet_file=SimpleUploadedFile("master-sheet.pdf", b"%PDF-1.4\nmaster", content_type="application/pdf"),
                end_of_days_file=SimpleUploadedFile(
                    "end-of-days.docx",
                    b"end-of-days",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            )

            detail_response = self.client.get(f"/end-of-day/{record.pk}/")
            preview_response = self.client.get(f"/end-of-day/{record.pk}/file/master-sheet/preview/")
            download_response = self.client.get(f"/end-of-day/{record.pk}/file/master-sheet/")

        self.assertContains(detail_response, "Uploaded daysheets")
        self.assertContains(detail_response, "Master Sheet")
        self.assertContains(detail_response, "End Of Days")
        self.assertContains(detail_response, 'data-previewable="1"')
        self.assertContains(detail_response, 'data-previewable="0"')
        self.assertContains(detail_response, "Preview not available for this file type.")
        self.assertEqual(preview_response.status_code, 200)
        self.assertIn("inline", preview_response["Content-Disposition"])
        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment", download_response["Content-Disposition"])

    def test_endofday_form_has_file_upload_controls(self):
        response = self.client.get("/end-of-day/add/")

        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "Master Sheet")
        self.assertContains(response, "End Of Days")
        self.assertContains(response, "Delivery Docket")
        self.assertContains(response, "No file uploaded yet")
        self.assertContains(response, "Upload file")
        self.assertContains(response, "upload-card")
        self.assertContains(response, ".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx")

    def test_endofday_form_has_draft_and_submit_actions(self):
        response = self.client.get("/end-of-day/add/")

        self.assertContains(response, "Save Draft")
        self.assertContains(response, 'name="action" value="save_draft"')
        self.assertContains(response, "Submit")
        self.assertContains(response, 'name="action" value="submit"')

    def test_endofday_edit_form_shows_current_uploads_can_be_changed(self):
        with override_settings(MEDIA_ROOT=self.temp_media.name):
            record = EndOfDay.objects.create(
                user=self.user,
                date=timezone.localdate(),
                entered_by="Ridoy",
                total_sales=0,
                ezy_pin=0,
                less_surcharge=0,
                master_sheet_file=SimpleUploadedFile("master-sheet.pdf", b"%PDF-1.4\nmaster", content_type="application/pdf"),
                end_of_days_file=SimpleUploadedFile("end-of-days.pdf", b"%PDF-1.4\ndays", content_type="application/pdf"),
            )

            response = self.client.get(f"/end-of-day/{record.pk}/edit/")

        self.assertContains(response, "Current file: master-sheet")
        self.assertContains(response, "Current file: end-of-days")
        self.assertContains(response, "Change file", count=2)


class PdfContentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.supplier = Supplier.objects.create(user=self.user, name="Fuel Supplier")
        self.client.login(username="owner", password="test-pass")

    def test_endofday_pdf_omits_shop_rules_section(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get(f"/end-of-day/{record.pk}/pdf/")
        content = response.content

        self.assertNotIn(b"United / Shop Rules", content)
        self.assertNotIn(b"Formula", content)
        self.assertNotIn(b"Payouts", content)
        self.assertGreater(len(content), 1000)

    def test_endofday_daysheet_starts_with_date_row(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        rows = endofday_daysheet_rows(record)

        self.assertEqual(rows[0][0], "Date")
        self.assertNotEqual(rows[0], ("", ""))

    def test_endofday_daysheet_includes_adjusted_united_and_shop_deductions(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            store_value_charge=12,
            united_card=100,
            iou=5,
            drive_offs=2,
            cash=30,
            vault_drop=40,
            total_sales=100,
            total_fuel_sales=20,
            ezy_pin=6,
            less_surcharge=5,
        )

        rows = dict(endofday_daysheet_rows(record))

        self.assertIn("Uber Eats", rows)
        self.assertIn("Door Dash", rows)
        self.assertIn("Store Value Charge", rows)
        self.assertIn("IOU Payment", rows)
        self.assertEqual(rows["Cash"], Decimal("30"))
        self.assertEqual(rows["Vault Drop / Cash Drop"], Decimal("40"))
        self.assertEqual(rows["United Card"], Decimal("105"))
        self.assertEqual(rows["Gross Shop Sales"], Decimal("80"))
        self.assertEqual(rows["Less Surcharge"], Decimal("5"))
        self.assertEqual(rows["EZY Pin"], Decimal("6"))
        self.assertNotIn("Fuel Tank 1", rows)

    def test_endofday_fuel_dip_rows_are_separate_from_main_daysheet_rows(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            fuel_dip_1_name="E85 tank 1",
            fuel_dip_1_value=100,
            fuel_dip_2_name="Unleaded 91 tank 1",
            fuel_dip_2_value=200,
            fuel_dip_3_name="Unleaded 95 tank 1",
            fuel_dip_3_value=300,
            fuel_dip_4_name="Unleaded 98 tank 1",
            fuel_dip_4_value=400,
            fuel_dip_5_name="Diesel tank 1",
            fuel_dip_5_value=500,
            fuel_dip_6_name="Diesel tank 2",
            fuel_dip_6_value=600,
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        daysheet_rows = dict(endofday_daysheet_rows(record))
        fuel_dip_rows = dict(endofday_fuel_dip_rows(record))

        self.assertNotIn("Fuel Dip - E85 tank 1", daysheet_rows)
        self.assertEqual(fuel_dip_rows["Fuel Dip - E85 tank 1"], Decimal("100"))
        self.assertEqual(fuel_dip_rows["Fuel Dip - Unleaded 91 tank 1"], Decimal("200"))
        self.assertEqual(fuel_dip_rows["Fuel Dip - Unleaded 95 tank 1"], Decimal("300"))
        self.assertEqual(fuel_dip_rows["Fuel Dip - Unleaded 98 tank 1"], Decimal("400"))
        self.assertEqual(fuel_dip_rows["Fuel Dip - Diesel tank 1"], Decimal("500"))
        self.assertEqual(fuel_dip_rows["Fuel Dip - Diesel tank 2"], Decimal("600"))

    def test_endofday_detail_includes_store_value_and_payment_lines(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            store_value_charge=12,
            iou_payment=7,
            drive_off_payment=3,
            total_sales=100,
            total_fuel_sales=20,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get(f"/end-of-day/{record.pk}/")

        self.assertContains(response, "Store Value Charge")
        self.assertContains(response, "IOU Payment")
        self.assertContains(response, "Drive Off Payment")
        self.assertContains(response, "Total Fuel Sales")

    def test_endofday_detail_includes_shop_deductions_after_gross_sales(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=100,
            total_fuel_sales=20,
            ezy_pin=6,
            less_surcharge=5,
        )

        response = self.client.get(f"/end-of-day/{record.pk}/")
        body = response.content.decode()
        table_body = body[body.index('<table class="table table-dayend align-middle">') : body.index("</table>")]

        self.assertContains(response, "Gross Shop Sales")
        self.assertContains(response, "Less Surcharge")
        self.assertContains(response, "EZY Pin")
        self.assertLess(table_body.index("Gross Shop Sales"), table_body.index("Less Surcharge"))
        self.assertLess(table_body.index("Less Surcharge"), table_body.index("EZY Pin"))
        self.assertLess(table_body.index("EZY Pin"), table_body.index("Net Shop Sales"))

    def test_endofday_detail_includes_fuel_dip_section(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            fuel_dip_1_name="E85 tank 1",
            fuel_dip_1_value=100,
            fuel_dip_2_name="Unleaded 91 tank 1",
            fuel_dip_2_value=200,
            fuel_dip_6_name="Diesel tank 2",
            fuel_dip_6_value=600,
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get(f"/end-of-day/{record.pk}/")

        self.assertContains(response, "Fuel Dips")
        self.assertContains(response, "E85 tank 1")
        self.assertContains(response, "Unleaded 91 tank 1")
        self.assertContains(response, "Diesel tank 2")

    def test_endofday_pdf_can_download_after_preview(self):
        record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        preview_response = self.client.get(f"/end-of-day/{record.pk}/pdf/")
        download_response = self.client.get(f"/end-of-day/{record.pk}/pdf/?download=1")

        self.assertIn("inline", preview_response["Content-Disposition"])
        self.assertIn("attachment", download_response["Content-Disposition"])

    def test_endofday_pdf_keeps_full_daysheet_and_uploaded_daysheet_pages(self):
        with tempfile.TemporaryDirectory() as temp_media, override_settings(MEDIA_ROOT=temp_media):
            record = EndOfDay.objects.create(
                user=self.user,
                date=timezone.localdate(),
                site_name="Holtze",
                entered_by="Ridoy",
                united_card=100,
                store_value_charge=12,
                iou=5,
                drive_offs=2,
                fuel_dip_1_name="E85 tank 1",
                fuel_dip_1_value=100,
                fuel_dip_2_name="Unleaded 91 tank 1",
                fuel_dip_2_value=200,
                fuel_dip_6_name="Diesel tank 2",
                fuel_dip_6_value=600,
                total_sales=0,
                ezy_pin=0,
                less_surcharge=0,
                master_sheet_file=SimpleUploadedFile("master-sheet.pdf", sample_pdf_bytes("Master Sheet"), content_type="application/pdf"),
                end_of_days_file=SimpleUploadedFile("end-of-days.pdf", sample_pdf_bytes("End Of Days"), content_type="application/pdf"),
            )

            response = self.client.get(f"/end-of-day/{record.pk}/pdf/")
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertEqual(len(reader.pages), 4)
        self.assertIn("Holtze", text)
        self.assertIn("United Card", text)
        self.assertIn("$105.00", text)
        self.assertIn("Net Shop Sales", text)
        self.assertIn("Fuel Dips", text)
        self.assertIn("E85 tank 1", text)
        self.assertIn("Master Sheet", text)
        self.assertIn("End Of Days", text)

    def test_endofday_list_uses_pdf_preview_modal(self):
        EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get("/end-of-day/")

        self.assertContains(response, "Preview PDF")
        self.assertContains(response, "endofdayPreviewModal")
        self.assertContains(response, "?download=1")

    def test_endofday_export_buttons_preview_before_download(self):
        EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get("/end-of-day/")

        self.assertContains(response, "endofdayExportPreviewModal")
        self.assertContains(response, "data-export-label=\"End of Day PDF Report\"")
        self.assertContains(response, "data-export-label=\"End of Day Excel Report\"")
        self.assertContains(response, "data-export-label=\"End of Day CSV Report\"")
        self.assertContains(response, "Vault Drop / Cash Drop")

    def test_generated_invoice_pdf_is_inline_preview(self):
        upload = SimpleUploadedFile("invoice.pdf", b"invoice", content_type="application/pdf")
        invoice = Invoice.objects.create(
            user=self.user,
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            invoice_number="INV-PDF",
            invoice_file=upload,
            entered_by="Ridoy",
        )
        self.client.login(username="owner", password="test-pass")

        response = self.client.get(f"/invoices/{invoice.pk}/pdf/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])


class ReturnLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.client.login(username="owner", password="test-pass")

    def test_invoice_add_back_can_return_to_dashboard(self):
        response = self.client.get("/invoices/add/?next=/dashboard/")

        self.assertContains(response, 'href="/dashboard/"')

    def test_endofday_add_back_can_return_to_dashboard(self):
        response = self.client.get("/end-of-day/add/?next=/dashboard/")

        self.assertContains(response, 'href="/dashboard/"')

    def test_unsafe_next_url_falls_back(self):
        response = self.client.get("/invoices/add/?next=https://example.com/bad")

        self.assertContains(response, 'href="/invoices/"')

    def test_logged_in_account_name_shows_next_to_logout(self):
        response = self.client.get("/dashboard/")

        self.assertContains(response, "owner")
        self.assertContains(response, "Logout")


class SignupApprovalTests(TestCase):
    def test_signup_creates_inactive_user_waiting_for_admin_approval(self):
        response = self.client.post(
            "/signup/",
            {
                "username": "newstaff",
                "email": "newstaff@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        user = User.objects.get(username="newstaff")

        self.assertRedirects(response, "/accounts/login/")
        self.assertFalse(user.is_active)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_page_explains_admin_approval(self):
        response = self.client.get("/signup/")

        self.assertContains(response, "New accounts need admin approval")

    def test_inactive_user_cannot_login(self):
        User.objects.create_user(username="waiting", password="test-pass", is_active=False)

        login_ok = self.client.login(username="waiting", password="test-pass")
        response = self.client.post("/accounts/login/", {"username": "waiting", "password": "test-pass"})

        self.assertFalse(login_ok)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Please enter a correct")


class EndOfDayArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.client.login(username="owner", password="test-pass")
        self.record = EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

    def test_archive_hides_record_from_normal_list(self):
        response = self.client.post(f"/end-of-day/{self.record.pk}/archive/", {"next": "/dashboard/"})

        self.assertRedirects(response, "/dashboard/")
        self.record.refresh_from_db()
        self.assertIsNotNone(self.record.archived_at)
        self.assertFalse(EndOfDay.objects.filter(pk=self.record.pk, archived_at__isnull=True).exists())

    def test_archive_page_keeps_old_record_available(self):
        self.record.archive(self.user)

        response = self.client.get("/end-of-day/archived/")

        self.assertContains(response, "Ridoy")
        self.assertContains(response, "View")

    def test_archived_record_does_not_block_new_same_day_record(self):
        self.record.archive(self.user)
        form = EndOfDayForm(
            data={
                "date": timezone.localdate().isoformat(),
                "entered_by": "New Staff",
                "total_sales": "0",
                "total_fuel_sales": "0",
                "gross_shop_sales": "0",
                "ezy_pin": "0",
                "less_surcharge": "0",
                "fuel_dip_1_name": "E85 tank 1",
                "fuel_dip_1_value": "0",
                "fuel_dip_2_name": "Unleaded 91 tank 1",
                "fuel_dip_2_value": "0",
                "fuel_dip_3_name": "Unleaded 95 tank 1",
                "fuel_dip_3_value": "0",
                "fuel_dip_4_name": "Unleaded 98 tank 1",
                "fuel_dip_4_value": "0",
                "fuel_dip_5_name": "Diesel tank 1",
                "fuel_dip_5_value": "0",
                "fuel_dip_6_name": "Diesel tank 2",
                "fuel_dip_6_value": "0",
            },
            files={
                "master_sheet_file": SimpleUploadedFile("master-sheet.pdf", b"%PDF-1.4\nmaster", content_type="application/pdf"),
                "end_of_days_file": SimpleUploadedFile("end-of-days.pdf", b"%PDF-1.4\ndays", content_type="application/pdf"),
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)


class EndOfDayReportExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.client.login(username="owner", password="test-pass")

    def test_csv_report_includes_date_and_site_name(self):
        EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            site_name="Holtze",
            entered_by="Ridoy",
            cash=25,
            vault_drop=15,
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get("/end-of-day/export/csv/")

        self.assertContains(response, "Date,Site Name,Entered By")
        self.assertContains(response, "Holtze")
        self.assertContains(response, "Cash,Vault Drop / Cash Drop")
        self.assertContains(response, "$25.00,$15.00")

    def test_csv_report_excludes_fuel_dips(self):
        EndOfDay.objects.create(
            user=self.user,
            date=timezone.localdate(),
            entered_by="Ridoy",
            fuel_dip_1_name="E85 tank 1",
            fuel_dip_1_value=100,
            fuel_dip_2_name="Unleaded 91 tank 1",
            fuel_dip_2_value=200,
            fuel_dip_3_name="Unleaded 95 tank 1",
            fuel_dip_3_value=300,
            fuel_dip_4_name="Unleaded 98 tank 1",
            fuel_dip_4_value=400,
            fuel_dip_5_name="Diesel tank 1",
            fuel_dip_5_value=500,
            fuel_dip_6_name="Diesel tank 2",
            fuel_dip_6_value=600,
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get("/end-of-day/export/csv/")

        self.assertContains(response, "Date,Site Name,Entered By,Cash,Vault Drop / Cash Drop,United Card,Gross Shop Sales,Less Surcharge,EZY Pin,Net Shop Sales")
        self.assertNotContains(response, "Fuel Tank 1")
        self.assertNotContains(response, "E85 tank 1")
        self.assertNotContains(response, "Diesel tank 2")


class AccountRoleAccessTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="manager", password="test-pass")
        self.staff = User.objects.create_user(username="staff", password="test-pass")
        self.staff.profile.role = AccountRole.STAFF
        self.staff.profile.save()
        self.supplier = Supplier.objects.create(user=self.staff, name="Shared Supplier")
        self.invoice = Invoice.objects.create(
            user=self.staff,
            supplier=self.supplier,
            invoice_date=timezone.localdate(),
            invoice_number="STAFF-INV",
            invoice_file=SimpleUploadedFile("staff-invoice.pdf", b"invoice", content_type="application/pdf"),
            entered_by="Staff",
        )
        self.record = EndOfDay.objects.create(
            user=self.staff,
            date=timezone.localdate(),
            entered_by="Staff",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

    def test_staff_can_use_supplier_pages(self):
        self.client.login(username="staff", password="test-pass")

        list_response = self.client.get("/suppliers/")
        add_response = self.client.get("/suppliers/add/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(add_response.status_code, 200)
        self.assertContains(list_response, "Shared Supplier")

    def test_staff_dashboard_only_shows_invoice_work(self):
        self.client.login(username="staff", password="test-pass")

        response = self.client.get("/dashboard/")

        self.assertContains(response, "+ Add Invoice")
        self.assertContains(response, "Recent Invoices")
        self.assertContains(response, "Invoices")
        self.assertNotContains(response, "+ Add End of Day")
        self.assertNotContains(response, "Latest End of Day")
        self.assertNotContains(response, "End of Day Summary")
        self.assertNotContains(response, 'href="/end-of-day/"')

    def test_staff_cannot_access_endofday_pages(self):
        self.client.login(username="staff", password="test-pass")

        list_response = self.client.get("/end-of-day/")
        archived_response = self.client.get("/end-of-day/archived/")
        add_response = self.client.get("/end-of-day/add/")
        detail_response = self.client.get(f"/end-of-day/{self.record.pk}/")
        edit_response = self.client.get(f"/end-of-day/{self.record.pk}/edit/")
        pdf_response = self.client.get(f"/end-of-day/{self.record.pk}/pdf/")
        export_response = self.client.get("/end-of-day/export/csv/")

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(archived_response.status_code, 403)
        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(detail_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(pdf_response.status_code, 403)
        self.assertEqual(export_response.status_code, 403)

    def test_staff_cannot_archive_endofday(self):
        self.client.login(username="staff", password="test-pass")

        response = self.client.post(f"/end-of-day/{self.record.pk}/archive/", {"next": "/dashboard/"})

        self.assertEqual(response.status_code, 403)
        self.record.refresh_from_db()
        self.assertIsNone(self.record.archived_at)

    def test_manager_can_add_endofday(self):
        self.client.login(username="manager", password="test-pass")

        response = self.client.get("/end-of-day/add/")

        self.assertEqual(response.status_code, 200)

    def test_manager_can_see_staff_records(self):
        self.client.login(username="manager", password="test-pass")

        invoice_response = self.client.get("/invoices/")
        endofday_response = self.client.get("/end-of-day/")

        self.assertContains(invoice_response, "STAFF-INV")
        self.assertContains(endofday_response, "Staff")

    def test_accounts_are_limited_to_their_site(self):
        site_two = StoreSite.objects.create(name="Site 2 Test")
        other_manager = User.objects.create_user(username="manager-two", password="test-pass")
        other_manager.profile.site = site_two
        other_manager.profile.save()
        other_staff = User.objects.create_user(username="staff-two", password="test-pass")
        other_staff.profile.role = AccountRole.STAFF
        other_staff.profile.site = site_two
        other_staff.profile.save()
        other_supplier = Supplier.objects.create(user=other_staff, site=site_two, name="Other Site Supplier")
        other_invoice = Invoice.objects.create(
            user=other_staff,
            site=site_two,
            supplier=other_supplier,
            invoice_date=timezone.localdate(),
            invoice_number="OTHER-SITE-INV",
            invoice_file=SimpleUploadedFile("other-invoice.pdf", b"invoice", content_type="application/pdf"),
            entered_by="Other Staff",
        )
        other_record = EndOfDay.objects.create(
            user=other_staff,
            site=site_two,
            date=timezone.localdate(),
            entered_by="Other Staff",
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        self.client.login(username="manager", password="test-pass")

        invoice_response = self.client.get("/invoices/")
        supplier_response = self.client.get("/suppliers/")
        endofday_response = self.client.get("/end-of-day/")
        other_invoice_detail = self.client.get(f"/invoices/{other_invoice.pk}/")
        other_endofday_detail = self.client.get(f"/end-of-day/{other_record.pk}/")

        self.assertContains(invoice_response, "STAFF-INV")
        self.assertNotContains(invoice_response, "OTHER-SITE-INV")
        self.assertContains(supplier_response, "Shared Supplier")
        self.assertNotContains(supplier_response, "Other Site Supplier")
        self.assertContains(endofday_response, "Staff")
        self.assertNotContains(endofday_response, "Other Staff")
        self.assertEqual(other_invoice_detail.status_code, 404)
        self.assertEqual(other_endofday_detail.status_code, 404)

    def test_admin_can_see_all_sites(self):
        site_two = StoreSite.objects.create(name="Site 2 Test")
        other_staff = User.objects.create_user(username="staff-two", password="test-pass")
        other_staff.profile.role = AccountRole.STAFF
        other_staff.profile.site = site_two
        other_staff.profile.save()
        other_supplier = Supplier.objects.create(user=other_staff, site=site_two, name="Other Site Supplier")
        Invoice.objects.create(
            user=other_staff,
            site=site_two,
            supplier=other_supplier,
            invoice_date=timezone.localdate(),
            invoice_number="OTHER-SITE-INV",
            invoice_file=SimpleUploadedFile("other-invoice.pdf", b"invoice", content_type="application/pdf"),
            entered_by="Other Staff",
        )
        admin = User.objects.create_superuser(username="admin", password="test-pass")

        self.client.login(username="admin", password="test-pass")
        response = self.client.get("/invoices/")

        self.assertContains(response, "STAFF-INV")
        self.assertContains(response, "OTHER-SITE-INV")
