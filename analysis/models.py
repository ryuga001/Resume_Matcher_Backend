from django.db import models


class Analysis(models.Model):
    user_id = models.IntegerField(db_index=True)
    resume_id = models.IntegerField(db_index=True)
    resume_name = models.CharField(max_length=255)
    job_description = models.TextField()
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analyses"
        ordering = ["-created_at"]
