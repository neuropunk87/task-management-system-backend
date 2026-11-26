from django.db import migrations, models


def disable_unverified_notifications(apps, schema_editor):
    # Preserve historical IDs, but require their owners to prove the private chat.
    user = apps.get_model("users", "CustomUser")
    user.objects.using(schema_editor.connection.alias).update(telegram_notifications_enabled=False)


class Migration(migrations.Migration):
    dependencies = [("users", "0002_telegramlinktoken")]
    operations = [
        migrations.AddField(
            model_name="customuser", name="telegram_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(disable_unverified_notifications, migrations.RunPython.noop),
    ]
