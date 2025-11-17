from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("itinerary", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="itinerary",
            name="ai_itinerary",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
