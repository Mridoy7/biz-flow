from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_sites_and_assign_existing_data(apps, schema_editor):
    StoreSite = apps.get_model("gst_app", "StoreSite")
    UserProfile = apps.get_model("gst_app", "UserProfile")
    Supplier = apps.get_model("gst_app", "Supplier")
    Invoice = apps.get_model("gst_app", "Invoice")
    EndOfDay = apps.get_model("gst_app", "EndOfDay")

    site_1, _ = StoreSite.objects.get_or_create(name="Site 1")
    StoreSite.objects.get_or_create(name="Site 2")

    UserProfile.objects.filter(site__isnull=True).update(site=site_1)
    Supplier.objects.filter(site__isnull=True).update(site=site_1)
    Invoice.objects.filter(site__isnull=True).update(site=site_1)
    EndOfDay.objects.filter(site__isnull=True).update(site=site_1)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("gst_app", "0011_endofday_dynamic_fuel_dips"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, unique=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="userprofile",
            name="site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="user_profiles",
                to="gst_app.storesite",
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="suppliers",
                to="gst_app.storesite",
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoices",
                to="gst_app.storesite",
            ),
        ),
        migrations.AddField(
            model_name="endofday",
            name="site",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="end_of_day_records",
                to="gst_app.storesite",
            ),
        ),
        migrations.RunPython(seed_sites_and_assign_existing_data, migrations.RunPython.noop),
    ]
