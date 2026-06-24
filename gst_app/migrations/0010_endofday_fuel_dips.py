from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0009_endofday_upload_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_e85",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_unleaded_91",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_unleaded_95",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_unleaded_98",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_diesel",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
