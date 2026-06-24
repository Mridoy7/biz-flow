from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0008_endofday_total_fuel_sales"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="master_sheet_file",
            field=models.FileField(blank=True, upload_to="end-of-day/master-sheets/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="endofday",
            name="end_of_days_file",
            field=models.FileField(blank=True, upload_to="end-of-day/end-of-days/%Y/%m/"),
        ),
    ]
