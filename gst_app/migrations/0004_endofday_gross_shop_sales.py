from decimal import Decimal

from django.db import migrations, models


def copy_total_sales_to_gross_shop_sales(apps, schema_editor):
    EndOfDay = apps.get_model("gst_app", "EndOfDay")
    for record in EndOfDay.objects.all():
        record.gross_shop_sales = record.total_sales
        record.net_shop_sales = record.gross_shop_sales - record.ezy_pin - record.less_surcharge
        record.save(update_fields=["gross_shop_sales", "net_shop_sales"])


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0003_active_endofday_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="gross_shop_sales",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.RunPython(copy_total_sales_to_gross_shop_sales, migrations.RunPython.noop),
    ]
