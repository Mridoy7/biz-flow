from django.contrib import admin

from .models import AuditLog, EndOfDay, Invoice, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at", "updated_at")
    search_fields = ("name", "user__username")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "supplier", "invoice_date", "invoice_amount", "user", "created_at")
    search_fields = ("invoice_number", "supplier__name", "entered_by")
    list_filter = ("invoice_date", "supplier")


@admin.register(EndOfDay)
class EndOfDayAdmin(admin.ModelAdmin):
    list_display = ("date", "entered_by", "total_sales", "total_value", "difference", "user")
    list_filter = ("date",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("model_name", "object_id", "field_name", "user", "changed_at")
    search_fields = ("model_name", "object_id", "field_name", "old_value", "new_value")
