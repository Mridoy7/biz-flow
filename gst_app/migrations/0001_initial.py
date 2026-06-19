from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("model_name", models.CharField(max_length=80)),
                ("object_id", models.CharField(max_length=80)),
                ("field_name", models.CharField(max_length=120)),
                ("old_value", models.TextField(blank=True)),
                ("new_value", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-changed_at"]},
        ),
        migrations.CreateModel(
            name="EndOfDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("entered_by", models.CharField(max_length=120)),
                ("uber_eats", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("doordash", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("eftpos", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("amex_card", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("motorpass", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("motorcharge", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("fleet_card", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("diners_card", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("united_card", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("store_value_charge", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("iou", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("drive_offs", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("cash", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("vault_drop", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_sales", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("ezy_pin", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("less_surcharge", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("adjusted_united_card", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_value", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("difference", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("net_shop_sales", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("note", models.TextField(blank=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="end_of_day_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="suppliers", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_date", models.DateField()),
                ("invoice_number", models.CharField(max_length=120)),
                ("invoice_file", models.FileField(upload_to="invoices/%Y/%m/")),
                ("entered_by", models.CharField(max_length=120)),
                ("invoice_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("notes", models.TextField(blank=True)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="gst_app.supplier")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invoices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-invoice_date", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(fields=("user", "name"), name="unique_supplier_name_per_user"),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(fields=("user", "supplier", "invoice_number"), name="unique_invoice_number_per_supplier_user"),
        ),
        migrations.AddConstraint(
            model_name="endofday",
            constraint=models.UniqueConstraint(fields=("user", "date"), name="unique_end_of_day_per_user_date"),
        ),
    ]
