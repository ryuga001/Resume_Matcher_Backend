from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resumes", "0002_resume_s3_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="customized_s3_key",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="resume",
            name="structured_data",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
