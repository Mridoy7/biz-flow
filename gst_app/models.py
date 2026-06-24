from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone


MONEY_ZERO = Decimal("0.00")


class AccountRole(models.TextChoices):
    STAFF = "staff", "Staff"
    MANAGER = "manager", "Manager"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=AccountRole.choices, default=AccountRole.MANAGER)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


def account_role(user):
    if not user.is_authenticated:
        return AccountRole.STAFF
    if user.is_superuser:
        return AccountRole.MANAGER
    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        return AccountRole.MANAGER


def is_manager(user):
    return account_role(user) == AccountRole.MANAGER


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Supplier(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=160)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_supplier_name_per_user"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("supplier_list")


class Invoice(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="invoices")
    invoice_date = models.DateField()
    invoice_number = models.CharField(max_length=120)
    invoice_file = models.FileField(upload_to="invoices/%Y/%m/")
    entered_by = models.CharField(max_length=120)
    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "supplier", "invoice_number"],
                name="unique_invoice_number_per_supplier_user",
            ),
        ]

    def __str__(self):
        return f"{self.supplier} - {self.invoice_number}"

    @property
    def original_invoice_is_previewable(self):
        if not self.invoice_file:
            return False
        return self.invoice_file.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"))

    def get_absolute_url(self):
        return reverse("invoice_detail", kwargs={"pk": self.pk})


class EndOfDay(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="end_of_day_records")
    date = models.DateField()
    site_name = models.CharField(max_length=120, blank=True)
    entered_by = models.CharField(max_length=120)
    uber_eats = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    doordash = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    eftpos = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    amex_card = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    motorpass = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    motorcharge = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fleet_card = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    diners_card = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    united_card = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    store_value_charge = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    iou = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    drive_offs = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    iou_payment = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    drive_off_payment = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    cash = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    vault_drop = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    total_fuel_sales = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    gross_shop_sales = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    ezy_pin = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    less_surcharge = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    adjusted_united_card = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    difference = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    net_shop_sales = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_e85 = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_unleaded_91 = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_unleaded_95 = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_unleaded_98 = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_diesel = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_1_name = models.CharField(max_length=120, blank=True)
    fuel_dip_1_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_2_name = models.CharField(max_length=120, blank=True)
    fuel_dip_2_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_3_name = models.CharField(max_length=120, blank=True)
    fuel_dip_3_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_4_name = models.CharField(max_length=120, blank=True)
    fuel_dip_4_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_5_name = models.CharField(max_length=120, blank=True)
    fuel_dip_5_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    fuel_dip_6_name = models.CharField(max_length=120, blank=True)
    fuel_dip_6_value = models.DecimalField(max_digits=12, decimal_places=2, default=MONEY_ZERO)
    master_sheet_file = models.FileField(upload_to="end-of-day/master-sheets/%Y/%m/", blank=True)
    end_of_days_file = models.FileField(upload_to="end-of-day/end-of-days/%Y/%m/", blank=True)
    note = models.TextField(blank=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="archived_end_of_day_records",
    )

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                condition=Q(archived_at__isnull=True),
                name="unique_active_end_of_day_per_user_date",
            ),
        ]

    def __str__(self):
        return f"End of Day {self.date}"

    @property
    def line_items(self):
        return [
            ("Uber Eats", self.uber_eats),
            ("DoorDash", self.doordash),
            ("EFTPOS", self.eftpos),
            ("Amex Card", self.amex_card),
            ("Motorpass", self.motorpass),
            ("Motorcharge", self.motorcharge),
            ("Fleet Card", self.fleet_card),
            ("Diners Card", self.diners_card),
            ("United Card", self.united_card),
            ("Store Value Charge", self.store_value_charge),
            ("Adjusted United Card", self.adjusted_united_card),
            ("IOU", self.iou),
            ("Drive Offs", self.drive_offs),
            ("IOU Payment", self.iou_payment),
            ("Drive Off Payment", self.drive_off_payment),
            ("Cash", self.cash),
            ("Vault Drop / Cash Drop", self.vault_drop),
        ]

    @property
    def fuel_dip_items(self):
        return [
            (getattr(self, f"fuel_dip_{index}_name", "").strip() or f"Fuel dip {index}", getattr(self, f"fuel_dip_{index}_value"))
            for index in range(1, 7)
        ]

    @property
    def total_sales_with_payments(self):
        return self.total_sales + self.iou_payment + self.drive_off_payment

    def calculate(self):
        self.adjusted_united_card = self.united_card + self.store_value_charge - self.iou - self.drive_offs
        self.total_value = sum((amount for label, amount in self.line_items if label not in {"United Card", "Store Value Charge"}), MONEY_ZERO)
        self.difference = self.total_value - self.total_sales_with_payments
        self.gross_shop_sales = self.total_sales_with_payments - self.total_fuel_sales
        self.net_shop_sales = self.gross_shop_sales - self.ezy_pin - self.less_surcharge

    def clean(self):
        self.calculate()
        if abs(self.difference) > Decimal("5.00") and not self.note.strip():
            raise ValidationError({"note": "A note is required when the difference is more than $5."})

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)

    @property
    def is_archived(self):
        return self.archived_at is not None

    def file_is_previewable(self, field_name):
        uploaded = getattr(self, field_name)
        if not uploaded:
            return False
        return uploaded.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"))

    @property
    def master_sheet_is_previewable(self):
        return self.file_is_previewable("master_sheet_file")

    @property
    def end_of_days_is_previewable(self):
        return self.file_is_previewable("end_of_days_file")

    def archive(self, user):
        self.archived_at = timezone.now()
        self.archived_by = user
        self.save(update_fields=["archived_at", "archived_by", "updated_at"])

    def get_absolute_url(self):
        return reverse("endofday_detail", kwargs={"pk": self.pk})


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    model_name = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    field_name = models.CharField(max_length=120)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.model_name} {self.object_id}: {self.field_name}"
