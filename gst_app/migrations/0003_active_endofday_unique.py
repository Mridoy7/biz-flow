from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("gst_app", "0002_endofday_archive"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="endofday",
            name="unique_end_of_day_per_user_date",
        ),
        migrations.AddConstraint(
            model_name="endofday",
            constraint=models.UniqueConstraint(
                fields=("user", "date"),
                condition=Q(("archived_at__isnull", True)),
                name="unique_active_end_of_day_per_user_date",
            ),
        ),
    ]
