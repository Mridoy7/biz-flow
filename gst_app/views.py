import csv
import mimetypes
from pathlib import Path
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from openpyxl import Workbook

from .forms import EndOfDayForm, EndOfDayReportForm, InvoiceForm, InvoiceReportForm, SignupForm, SupplierForm
from .models import EndOfDay, Invoice, InvoiceAttachment, Supplier, is_manager, user_site
from .pdf import endofday_pdf, invoice_pdf, merged_invoice_upload_pdf_bytes, money, report_pdf
from .services import snapshot_instance, write_audit_logs


def safe_next_url(request, fallback):
    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return fallback


def require_dayend_manager(user):
    if not is_manager(user):
        raise PermissionDenied("Only managers can access End of Day records.")


def owned_or_all(queryset, user):
    if user.is_superuser:
        return queryset
    site = user_site(user)
    if site:
        return queryset.filter(site=site)
    return queryset.none()


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "gst_app/home.html")


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created. Welcome.")
            return redirect("dashboard")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard(request):
    invoices = owned_or_all(Invoice.objects.all(), request.user)
    context = {
        "invoice_count": invoices.count(),
        "recent_invoices": invoices.select_related("supplier")[:5],
    }
    if is_manager(request.user):
        endofday_records = owned_or_all(EndOfDay.objects.filter(archived_at__isnull=True), request.user)
        context.update(
            {
                "latest_endofday": endofday_records.first(),
                "recent_endofday": endofday_records[:5],
            }
        )
    return render(request, "gst_app/dashboard.html", context)


@login_required
def supplier_list(request):
    query = request.GET.get("q", "")
    suppliers = owned_or_all(Supplier.objects.all(), request.user)
    if query:
        suppliers = suppliers.filter(name__icontains=query)
    return render(request, "gst_app/supplier_list.html", {"suppliers": suppliers, "query": query})


@login_required
def supplier_form(request, pk=None):
    supplier = None
    if pk:
        supplier = get_object_or_404(owned_or_all(Supplier.objects.all(), request.user), pk=pk)
    before = snapshot_instance(supplier, ["name"]) if supplier else {}
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            saved = form.save(commit=False)
            if not saved.pk:
                saved.user = request.user
            if not saved.site_id:
                saved.site = user_site(request.user)
            saved.save()
            write_audit_logs(request.user, saved, before, ["name"])
            messages.success(request, "Supplier saved.")
            return redirect("supplier_list")
    else:
        form = SupplierForm(instance=supplier)
    return render(request, "gst_app/form.html", {"form": form, "title": "Supplier", "cancel_url": reverse("supplier_list")})


@login_required
def invoice_list(request):
    form = InvoiceReportForm(request.GET or None, user=request.user)
    invoices = filter_invoices(request.user, request.GET)
    return render(request, "gst_app/invoice_list.html", {"invoices": invoices, "form": form})


def filter_invoices(user, params):
    invoices = owned_or_all(Invoice.objects.all(), user).select_related("supplier")
    supplier = params.get("supplier")
    invoice_number = params.get("invoice_number")
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if supplier:
        invoices = invoices.filter(supplier_id=supplier)
    if invoice_number:
        invoices = invoices.filter(invoice_number__icontains=invoice_number)
    if start_date:
        invoices = invoices.filter(invoice_date__gte=start_date)
    if end_date:
        invoices = invoices.filter(invoice_date__lte=end_date)
    return invoices


def invoice_attachments_for_user(user):
    attachments = InvoiceAttachment.objects.select_related("invoice")
    if user.is_superuser:
        return attachments
    site = user_site(user)
    if site:
        return attachments.filter(invoice__site=site)
    return attachments.none()


def save_new_invoice_attachments(invoice, uploaded_files, user):
    for uploaded_file in uploaded_files:
        InvoiceAttachment.objects.create(invoice=invoice, file=uploaded_file, uploaded_by=user)


def delete_invoice_attachments(invoice):
    for attachment in invoice.attachments.all():
        if attachment.file:
            attachment.file.delete(save=False)
        attachment.delete()


def replace_invoice_pages(invoice, uploaded_files, user, old_invoice_file=None):
    if not uploaded_files:
        return
    if old_invoice_file:
        old_invoice_file.delete(save=False)
    delete_invoice_attachments(invoice)
    save_new_invoice_attachments(invoice, uploaded_files[1:], user)


def add_invoice_pages(invoice, uploaded_files, user):
    if not uploaded_files:
        return
    if not invoice.invoice_file:
        invoice.invoice_file = uploaded_files[0]
        invoice.save(update_fields=["invoice_file", "updated_at"])
        save_new_invoice_attachments(invoice, uploaded_files[1:], user)
        return
    save_new_invoice_attachments(invoice, uploaded_files, user)


def update_invoice_attachments(request, invoice):
    attachment_ids_to_delete = set(request.POST.getlist("delete_attachments"))
    attachments = invoice.attachments.all()
    for attachment in attachments:
        replacement = request.FILES.get(f"replace_attachment_{attachment.pk}")
        should_delete = str(attachment.pk) in attachment_ids_to_delete
        if should_delete:
            if attachment.file:
                attachment.file.delete(save=False)
            attachment.delete()
            continue
        if replacement:
            if attachment.file:
                attachment.file.delete(save=False)
            attachment.file = replacement
            attachment.uploaded_by = request.user
            attachment.save(update_fields=["file", "uploaded_by", "updated_at"])


@login_required
def invoice_form(request, pk=None):
    invoice = None
    if pk:
        invoice = get_object_or_404(owned_or_all(Invoice.objects.all(), request.user), pk=pk)
    cancel_url = safe_next_url(request, reverse("invoice_list"))
    before = snapshot_instance(invoice, ["supplier", "invoice_date", "invoice_number", "entered_by", "invoice_amount", "notes"]) if invoice else {}
    if request.method == "POST":
        form = InvoiceForm(request.POST, request.FILES, instance=invoice, user=request.user)
        if form.is_valid():
            saved = form.save(commit=False)
            invoice_pages = form.cleaned_data.get("invoice_pages", [])
            if not saved.pk:
                saved.user = request.user
            if not saved.site_id:
                saved.site = saved.supplier.site or user_site(request.user)
            if invoice_pages and not saved.pk:
                saved.invoice_file = invoice_pages[0]
            saved.save()
            if invoice_pages:
                if invoice:
                    add_invoice_pages(saved, invoice_pages, request.user)
                else:
                    replace_invoice_pages(saved, invoice_pages, request.user)
            update_invoice_attachments(request, saved)
            write_audit_logs(request.user, saved, before, ["supplier", "invoice_date", "invoice_number", "entered_by", "invoice_amount", "notes"])
            messages.success(request, "Invoice saved.")
            return redirect(saved)
    else:
        form = InvoiceForm(instance=invoice, user=request.user)
    attachments = invoice.attachments.all() if invoice else []
    invoice_page_count = (1 + len(attachments)) if invoice and invoice.invoice_file else 0
    return render(
        request,
        "gst_app/invoice_form.html",
        {
            "form": form,
            "invoice": invoice,
            "attachments": attachments,
            "invoice_page_count": invoice_page_count,
            "title": "Invoice",
            "cancel_url": cancel_url,
        },
    )


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(owned_or_all(Invoice.objects.select_related("supplier"), request.user), pk=pk)
    return render(request, "gst_app/invoice_detail.html", {"invoice": invoice})


@login_required
@xframe_options_sameorigin
def invoice_pdf_view(request, pk):
    invoice = get_object_or_404(owned_or_all(Invoice.objects.select_related("supplier"), request.user), pk=pk)
    return invoice_pdf(invoice)


@login_required
def invoice_file_download(request, pk):
    invoice = get_object_or_404(owned_or_all(Invoice.objects.prefetch_related("attachments"), request.user), pk=pk)
    if not invoice.invoice_file:
        raise Http404("No uploaded invoice file found.")
    merged_pdf = merged_invoice_upload_pdf_bytes(invoice)
    if merged_pdf:
        response = HttpResponse(merged_pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice-{invoice.pk}-pages.pdf"'
        return response
    filename = Path(invoice.invoice_file.name).name
    return FileResponse(invoice.invoice_file.open("rb"), as_attachment=True, filename=filename)


@login_required
@xframe_options_sameorigin
def invoice_file_preview(request, pk):
    invoice = get_object_or_404(owned_or_all(Invoice.objects.prefetch_related("attachments"), request.user), pk=pk)
    if not invoice.invoice_file:
        raise Http404("No uploaded invoice file found.")
    merged_pdf = merged_invoice_upload_pdf_bytes(invoice)
    if merged_pdf:
        response = HttpResponse(merged_pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="invoice-{invoice.pk}-pages.pdf"'
        return response
    filename = Path(invoice.invoice_file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(invoice.invoice_file.open("rb"), as_attachment=False, filename=filename, content_type=content_type)


@login_required
def invoice_attachment_download(request, pk):
    attachment = get_object_or_404(invoice_attachments_for_user(request.user), pk=pk)
    if not attachment.file:
        raise Http404("No uploaded invoice attachment found.")
    filename = Path(attachment.file.name).name
    return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=filename)


@login_required
@xframe_options_sameorigin
def invoice_attachment_preview(request, pk):
    attachment = get_object_or_404(invoice_attachments_for_user(request.user), pk=pk)
    if not attachment.file:
        raise Http404("No uploaded invoice attachment found.")
    filename = Path(attachment.file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(attachment.file.open("rb"), as_attachment=False, filename=filename, content_type=content_type)


def endofday_uploaded_file(record, file_kind):
    if file_kind == "master-sheet":
        return record.master_sheet_file, "Master Sheet"
    if file_kind == "end-of-days":
        return record.end_of_days_file, "End Of Days"
    raise Http404("Unknown End of Day file.")


@login_required
def endofday_list(request):
    require_dayend_manager(request.user)
    form = EndOfDayReportForm(request.GET or None)
    records = filter_endofday(request.user, request.GET)
    return render(request, "gst_app/endofday_list.html", {"records": records, "form": form})


@login_required
def archived_endofday_list(request):
    require_dayend_manager(request.user)
    records = owned_or_all(EndOfDay.objects.filter(archived_at__isnull=False), request.user)
    return render(request, "gst_app/archived_endofday_list.html", {"records": records})


def filter_endofday(user, params):
    records = owned_or_all(EndOfDay.objects.filter(archived_at__isnull=True), user)
    today = timezone.localdate()
    period = params.get("period")
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if period == "today":
        start_date = end_date = today
    elif period == "yesterday":
        start_date = end_date = today - timedelta(days=1)
    elif period == "last_7_days":
        start_date = today - timedelta(days=6)
        end_date = today
    elif period == "last_month":
        start_date = today - timedelta(days=30)
        end_date = today
    if start_date:
        records = records.filter(date__gte=start_date)
    if end_date:
        records = records.filter(date__lte=end_date)
    return records


@login_required
def endofday_form(request, pk=None):
    require_dayend_manager(request.user)
    record = None
    if pk:
        record = get_object_or_404(owned_or_all(EndOfDay.objects.filter(archived_at__isnull=True), request.user), pk=pk)
    cancel_url = safe_next_url(request, reverse("endofday_list"))
    audited_fields = EndOfDayForm.money_fields + EndOfDayForm.fuel_dip_fields + [
        "date",
        "site_name",
        "entered_by",
        "master_sheet_file",
        "end_of_days_file",
        "note",
    ]
    before = snapshot_instance(record, audited_fields) if record else {}
    if request.method == "POST":
        form = EndOfDayForm(request.POST, request.FILES, instance=record, user=request.user)
        if form.is_valid():
            saved = form.save(commit=False)
            if not saved.pk:
                saved.user = request.user
            if not saved.site_id:
                saved.site = user_site(request.user)
            saved.full_clean()
            saved.save()
            write_audit_logs(request.user, saved, before, audited_fields)
            messages.success(request, "End of Day saved. PDF is ready to download.")
            return redirect(saved)
    else:
        form = EndOfDayForm(instance=record, user=request.user)
    return render(request, "gst_app/endofday_form.html", {"form": form, "record": record, "cancel_url": cancel_url})


@login_required
def endofday_detail(request, pk):
    require_dayend_manager(request.user)
    record = get_object_or_404(owned_or_all(EndOfDay.objects.all(), request.user), pk=pk)
    return render(request, "gst_app/endofday_detail.html", {"record": record})


@login_required
@xframe_options_sameorigin
def endofday_pdf_view(request, pk):
    require_dayend_manager(request.user)
    record = get_object_or_404(owned_or_all(EndOfDay.objects.all(), request.user), pk=pk)
    return endofday_pdf(record, as_attachment=request.GET.get("download") == "1")


@login_required
def endofday_file_download(request, pk, file_kind):
    require_dayend_manager(request.user)
    record = get_object_or_404(owned_or_all(EndOfDay.objects.all(), request.user), pk=pk)
    uploaded, label = endofday_uploaded_file(record, file_kind)
    if not uploaded:
        raise Http404(f"No {label} file found.")
    filename = Path(uploaded.name).name
    return FileResponse(uploaded.open("rb"), as_attachment=True, filename=filename)


@login_required
@xframe_options_sameorigin
def endofday_file_preview(request, pk, file_kind):
    require_dayend_manager(request.user)
    record = get_object_or_404(owned_or_all(EndOfDay.objects.all(), request.user), pk=pk)
    uploaded, label = endofday_uploaded_file(record, file_kind)
    if not uploaded:
        raise Http404(f"No {label} file found.")
    filename = Path(uploaded.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(uploaded.open("rb"), as_attachment=False, filename=filename, content_type=content_type)


@login_required
def endofday_archive(request, pk):
    require_dayend_manager(request.user)
    record = get_object_or_404(owned_or_all(EndOfDay.objects.filter(archived_at__isnull=True), request.user), pk=pk)
    if request.method != "POST":
        raise PermissionDenied
    record.archive(request.user)
    messages.success(request, "End of Day moved to archive.")
    return redirect(safe_next_url(request, reverse("dashboard")))


@login_required
@xframe_options_sameorigin
def invoice_export(request, filetype):
    invoices = filter_invoices(request.user, request.GET)
    rows = [[i.supplier.name, i.invoice_date, i.invoice_number, i.entered_by, money(i.invoice_amount or 0), i.created_at] for i in invoices]
    headers = ["Supplier", "Invoice Date", "Invoice Number", "Entered By", "Amount", "Created"]
    return export_rows(request, filetype, "invoice-report", headers, rows)


@login_required
@xframe_options_sameorigin
def endofday_export(request, filetype):
    require_dayend_manager(request.user)
    records = filter_endofday(request.user, request.GET)
    rows = [
        [
            r.date,
            r.site_name or "-",
            r.entered_by,
            money(r.cash),
            money(r.vault_drop),
            money(r.total_sales_with_payments),
            money(r.total_fuel_sales),
            r.fuel_dip_1_name or "-",
            f"{r.fuel_dip_1_value:,.2f}",
            r.fuel_dip_2_name or "-",
            f"{r.fuel_dip_2_value:,.2f}",
            r.fuel_dip_3_name or "-",
            f"{r.fuel_dip_3_value:,.2f}",
            r.fuel_dip_4_name or "-",
            f"{r.fuel_dip_4_value:,.2f}",
            r.fuel_dip_5_name or "-",
            f"{r.fuel_dip_5_value:,.2f}",
            r.fuel_dip_6_name or "-",
            f"{r.fuel_dip_6_value:,.2f}",
            money(r.gross_shop_sales),
            money(r.total_value),
            money(r.difference),
            money(r.net_shop_sales),
        ]
        for r in records
    ]
    headers = [
        "Date",
        "Site Name",
        "Entered By",
        "Cash",
        "Vault Drop / Cash Drop",
        "Terminal Total",
        "Total Fuel Sales",
        "Fuel Dip 1",
        "Dip Value 1",
        "Fuel Dip 2",
        "Dip Value 2",
        "Fuel Dip 3",
        "Dip Value 3",
        "Fuel Dip 4",
        "Dip Value 4",
        "Fuel Dip 5",
        "Dip Value 5",
        "Fuel Dip 6",
        "Dip Value 6",
        "Gross Shop Sales",
        "Total sales",
        "Difference",
        "Net Shop Sales",
    ]
    return export_rows(request, filetype, "end-of-day-report", headers, rows)


def export_rows(request, filetype, basename, headers, rows):
    if filetype == "pdf":
        return report_pdf(
            f"{basename}.pdf",
            basename.replace("-", " ").title(),
            headers,
            rows,
            as_attachment=request.GET.get("download") == "1",
        )
    if filetype == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Report"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{basename}.xlsx"'
        workbook.save(response)
        return response
    if filetype == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{basename}.csv"'
        writer = csv.writer(response)
        writer.writerow(headers)
        writer.writerows(rows)
        return response
    raise PermissionDenied
