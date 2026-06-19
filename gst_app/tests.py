from datetime import date
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from .forms import EndOfDayForm, InvoiceForm
from .models import AccountRole, EndOfDay, Invoice, Supplier
from .pdf import endofday_daysheet_rows


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

    def test_net_shop_sales_uses_gross_shop_sales(self):
        record = self.make_record(total_sales=500, gross_shop_sales=370, ezy_pin=20, less_surcharge=5, note="Explained")
        record.full_clean()

        self.assertEqual(record.difference, Decimal("-120"))
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
            files={"invoice_file": upload},
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
            files={"invoice_file": duplicate_upload},
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("This invoice number already exists for this supplier.", form.errors["invoice_number"])

    def test_endofday_form_rejects_previous_day(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        form = EndOfDayForm(
            data={
                "date": yesterday.isoformat(),
                "site_name": "Holtze",
                "entered_by": "Ridoy",
                "ezy_pin": "0",
                "less_surcharge": "0",
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("End of Day date must be today's date.", form.errors["date"])

    def test_endofday_form_accepts_site_name(self):
        today = timezone.localdate()
        form = EndOfDayForm(
            data={
                "date": today.isoformat(),
                "site_name": "Holtze",
                "entered_by": "Ridoy",
                "total_sales": "0",
                "gross_shop_sales": "0",
                "ezy_pin": "0",
                "less_surcharge": "0",
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["site_name"], "Holtze")


class InvoiceFileDownloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="test-pass")
        self.supplier = Supplier.objects.create(user=self.user, name="Fuel Supplier")

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
                "gross_shop_sales": "0",
                "ezy_pin": "0",
                "less_surcharge": "0",
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
            total_sales=0,
            ezy_pin=0,
            less_surcharge=0,
        )

        response = self.client.get("/end-of-day/export/csv/")

        self.assertContains(response, "Date,Site Name,Entered By")
        self.assertContains(response, "Holtze")


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

    def test_staff_dashboard_hides_add_endofday(self):
        self.client.login(username="staff", password="test-pass")

        response = self.client.get("/dashboard/")

        self.assertContains(response, "+ Add Invoice")
        self.assertNotContains(response, "+ Add End of Day")

    def test_staff_cannot_add_or_edit_endofday(self):
        self.client.login(username="staff", password="test-pass")

        add_response = self.client.get("/end-of-day/add/")
        edit_response = self.client.get(f"/end-of-day/{self.record.pk}/edit/")

        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)

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
