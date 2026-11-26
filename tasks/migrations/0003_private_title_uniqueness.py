from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tasks", "0002_security_fields")]
    operations = [
        migrations.AlterField(model_name="task", name="title", field=models.CharField(max_length=255)),
        migrations.AddConstraint(
            model_name="task",
            constraint=models.UniqueConstraint(fields=("project", "title"), name="task_title_per_project"),
        ),
    ]
