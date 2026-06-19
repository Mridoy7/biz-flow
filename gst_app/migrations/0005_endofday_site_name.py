from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0004_endofday_gross_shop_sales"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="site_name",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
