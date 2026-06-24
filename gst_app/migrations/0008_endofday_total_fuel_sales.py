from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0007_endofday_iou_driveoff_payments"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="total_fuel_sales",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
    ]
