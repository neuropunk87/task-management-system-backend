from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_notification_dedupe_key"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dedupe_key", models.CharField(max_length=255, unique=True)),
                ("channel", models.CharField(choices=[("email", "Email"), ("telegram", "Telegram")], max_length=10)),
                ("destination", models.CharField(max_length=254)),
                ("subject", models.CharField(blank=True, max_length=300)),
                ("message", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("cancelled", "Cancelled"), ("failed", "Failed")], default="pending", max_length=10)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("available_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("lease_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("notification", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="notifications.notification")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["status", "available_at"], name="delivery_pending_idx")]},
        ),
    ]
