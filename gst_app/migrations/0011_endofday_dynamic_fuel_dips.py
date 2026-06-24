from django.db import migrations, models


def copy_fixed_fuel_dips(apps, schema_editor):
    EndOfDay = apps.get_model("gst_app", "EndOfDay")
    mappings = [
        (1, "E85", "fuel_dip_e85"),
        (2, "Unleaded 91", "fuel_dip_unleaded_91"),
        (3, "Unleaded 95", "fuel_dip_unleaded_95"),
        (4, "Unleaded 98", "fuel_dip_unleaded_98"),
        (5, "Diesel", "fuel_dip_diesel"),
    ]
    for record in EndOfDay.objects.all():
        update_fields = []
        for index, label, old_field in mappings:
            name_field = f"fuel_dip_{index}_name"
            value_field = f"fuel_dip_{index}_value"
            setattr(record, name_field, label)
            setattr(record, value_field, getattr(record, old_field))
            update_fields.extend([name_field, value_field])
        record.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0010_endofday_fuel_dips"),
    ]

    operations = [
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_1_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_1_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_2_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_2_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_3_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_3_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_4_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_4_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_5_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_5_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_6_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="endofday",
            name="fuel_dip_6_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(copy_fixed_fuel_dips, migrations.RunPython.noop),
    ]
