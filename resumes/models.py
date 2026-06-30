from django.db import models


class Resume(models.Model):
    user_id = models.IntegerField(db_index=True)
    file_name = models.CharField(max_length=255)
    resume_text = models.TextField()
    skills = models.JSONField(default=list)
    s3_key = models.CharField(max_length=500, blank=True, default="")
    customized_s3_key = models.CharField(max_length=500, blank=True, default="")
    structured_data = models.JSONField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    index_status = models.CharField(max_length=20, default="processing")

    class Meta:
        db_table = "resumes"
        ordering = ["-uploaded_at"]
