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
from openpyxl import Workbook

from .forms import EndOfDayForm, EndOfDayReportForm, InvoiceForm, InvoiceReportForm, SignupForm, SupplierForm
from .models import EndOfDay, Invoice, Supplier
from .pdf import endofday_pdf, invoice_pdf, money, report_pdf
from .services import snapshot_instance, write_audit_logs


def safe_next_url(request, fallback):
    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return fallback


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
    invoices = Invoice.objects.filter(user=request.user)
    endofday_records = EndOfDay.objects.filter(user=request.user, archived_at__isnull=True)
    context = {
        "invoice_count": invoices.count(),
        "recent_invoices": invoices.select_related("supplier")[:5],
        "latest_endofday": endofday_records.first(),
        "recent_endofday": endofday_records[:5],
    }
    return render(request, "gst_app/dashboard.html", context)


@login_required
def supplier_list(request):
    query = request.GET.get("q", "")
    suppliers = Supplier.objects.filter(user=request.user)
    if query:
        suppliers = suppliers.filter(name__icontains=query)
    return render(request, "gst_app/supplier_list.html", {"suppliers": suppliers, "query": query})


@login_required
def supplier_form(request, pk=None):
    supplier = None
    if pk:
        supplier = get_object_or_404(Supplier, pk=pk, user=request.user)
    before = snapshot_instance(supplier, ["name"]) if supplier else {}
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.user = request.user
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
    invoices = Invoice.objects.filter(user=user).select_related("supplier")
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


@login_required
def invoice_form(request, pk=None):
    invoice = None
    if pk:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    cancel_url = safe_next_url(request, reverse("invoice_list"))
    before = snapshot_instance(invoice, ["supplier", "invoice_date", "invoice_number", "entered_by", "invoice_amount", "notes"]) if invoice else {}
    if request.method == "POST":
        form = InvoiceForm(request.POST, request.FILES, instance=invoice, user=request.user)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.user = request.user
            saved.save()
            write_audit_logs(request.user, saved, before, ["supplier", "invoice_date", "invoice_number", "entered_by", "invoice_amount", "notes"])
            messages.success(request, "Invoice saved.")
            return redirect(saved)
    else:
        form = InvoiceForm(instance=invoice, user=request.user)
    return render(request, "gst_app/form.html", {"form": form, "title": "Invoice", "cancel_url": cancel_url})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("supplier"), pk=pk, user=request.user)
    return render(request, "gst_app/invoice_detail.html", {"invoice": invoice})


@login_required
def invoice_pdf_view(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("supplier"), pk=pk, user=request.user)
    return invoice_pdf(invoice)


@login_required
def invoice_file_download(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    if not invoice.invoice_file:
        raise Http404("No uploaded invoice file found.")
    filename = Path(invoice.invoice_file.name).name
    return FileResponse(invoice.invoice_file.open("rb"), as_attachment=True, filename=filename)


@login_required
def invoice_file_preview(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    if not invoice.invoice_file:
        raise Http404("No uploaded invoice file found.")
    filename = Path(invoice.invoice_file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(invoice.invoice_file.open("rb"), as_attachment=False, filename=filename, content_type=content_type)


@login_required
def endofday_list(request):
    form = EndOfDayReportForm(request.GET or None)
    records = filter_endofday(request.user, request.GET)
    return render(request, "gst_app/endofday_list.html", {"records": records, "form": form})


@login_required
def archived_endofday_list(request):
    records = EndOfDay.objects.filter(user=request.user, archived_at__isnull=False)
    return render(request, "gst_app/archived_endofday_list.html", {"records": records})


def filter_endofday(user, params):
    records = EndOfDay.objects.filter(user=user, archived_at__isnull=True)
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
    record = None
    if pk:
        record = get_object_or_404(EndOfDay, pk=pk, user=request.user, archived_at__isnull=True)
    cancel_url = safe_next_url(request, reverse("endofday_list"))
    before = snapshot_instance(record, EndOfDayForm.money_fields + ["date", "entered_by", "note"]) if record else {}
    if request.method == "POST":
        form = EndOfDayForm(request.POST, instance=record, user=request.user)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.user = request.user
            saved.full_clean()
            saved.save()
            write_audit_logs(request.user, saved, before, EndOfDayForm.money_fields + ["date", "entered_by", "note"])
            messages.success(request, "End of Day saved. PDF is ready to download.")
            return redirect(saved)
    else:
        form = EndOfDayForm(instance=record, user=request.user)
    return render(request, "gst_app/endofday_form.html", {"form": form, "record": record, "cancel_url": cancel_url})


@login_required
def endofday_detail(request, pk):
    record = get_object_or_404(EndOfDay, pk=pk, user=request.user)
    return render(request, "gst_app/endofday_detail.html", {"record": record})


@login_required
def endofday_pdf_view(request, pk):
    record = get_object_or_404(EndOfDay, pk=pk, user=request.user)
    return endofday_pdf(record)


@login_required
def endofday_archive(request, pk):
    record = get_object_or_404(EndOfDay, pk=pk, user=request.user, archived_at__isnull=True)
    if request.method != "POST":
        raise PermissionDenied
    record.archive(request.user)
    messages.success(request, "End of Day moved to archive.")
    return redirect(safe_next_url(request, reverse("dashboard")))


@login_required
def invoice_export(request, filetype):
    invoices = filter_invoices(request.user, request.GET)
    rows = [[i.supplier.name, i.invoice_date, i.invoice_number, i.entered_by, money(i.invoice_amount or 0), i.created_at] for i in invoices]
    headers = ["Supplier", "Invoice Date", "Invoice Number", "Entered By", "Amount", "Created"]
    return export_rows(filetype, "invoice-report", headers, rows)


@login_required
def endofday_export(request, filetype):
    records = filter_endofday(request.user, request.GET)
    rows = [[r.date, r.entered_by, money(r.total_sales), money(r.total_value), money(r.difference), money(r.net_shop_sales)] for r in records]
    headers = ["Date", "Entered By", "Total Sales", "Total Value", "Difference", "Net Shop Sales"]
    return export_rows(filetype, "end-of-day-report", headers, rows)


def export_rows(filetype, basename, headers, rows):
    if filetype == "pdf":
        return report_pdf(f"{basename}.pdf", basename.replace("-", " ").title(), headers, rows)
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
