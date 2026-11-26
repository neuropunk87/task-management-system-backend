from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]
    operations = [
        migrations.AlterField(
            model_name="project", name="name",
            field=models.CharField(help_text="Project name", max_length=255),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(fields=("owner", "name"), name="project_name_per_owner"),
        ),
    ]
