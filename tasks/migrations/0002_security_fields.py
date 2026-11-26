import django.db.models.deletion
from django.db import migrations, models


def backfill_completed_at(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Task.objects.filter(status="Completed", completed_at__isnull=True).update(
        completed_at=models.F("modified_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="replies",
                to="tasks.comment",
            ),
        ),
        migrations.AlterField(
            model_name="comment",
            name="modified_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="task",
            name="completed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill_completed_at, migrations.RunPython.noop),
    ]
