import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def synchronize_admin_flags(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    CustomUser.objects.filter(is_superuser=True).update(
        role="superadmin", is_staff=True
    )
    CustomUser.objects.filter(
        is_superuser=False, role__in=("admin", "superadmin")
    ).update(is_staff=True)
    CustomUser.objects.filter(
        is_superuser=False, role__in=("manager", "employee")
    ).update(is_staff=False)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramLinkToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="telegram_link_token",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.RunPython(synchronize_admin_flags, migrations.RunPython.noop),
    ]
