from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0006_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="iou_payment",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="drive_off_payment",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
    ]
