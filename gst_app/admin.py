from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import AuditLog, EndOfDay, Invoice, InvoiceAttachment, StoreSite, Supplier, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    verbose_name_plural = "Account role and site"


@admin.register(StoreSite)
class StoreSiteAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)


admin.site.unregister(User)


@admin.action(description="Approve selected users")
def approve_users(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    actions = (approve_users,)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "user", "created_at", "updated_at")
    search_fields = ("name", "site__name", "user__username")
    list_filter = ("site",)


class InvoiceAttachmentInline(admin.TabularInline):
    model = InvoiceAttachment
    extra = 0
    fields = ("file", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "supplier", "site", "invoice_date", "invoice_amount", "user", "created_at")
    search_fields = ("invoice_number", "supplier__name", "site__name", "entered_by")
    list_filter = ("site", "invoice_date", "supplier")
    inlines = (InvoiceAttachmentInline,)


@admin.register(InvoiceAttachment)
class InvoiceAttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "invoice", "uploaded_by", "created_at")
    search_fields = ("file", "invoice__invoice_number", "invoice__supplier__name")


@admin.register(EndOfDay)
class EndOfDayAdmin(admin.ModelAdmin):
    list_display = ("date", "site", "entered_by", "total_sales", "total_value", "difference", "user")
    list_filter = ("site", "date")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("model_name", "object_id", "field_name", "user", "changed_at")
    search_fields = ("model_name", "object_id", "field_name", "old_value", "new_value")
