from django.db import models
from pgvector.django import VectorField


class Course(models.Model):
    topic = models.CharField(max_length=500)
    categories = models.JSONField(default=list)
    status = models.CharField(max_length=50, default="Not Available")
    thumbnail_key = models.CharField(max_length=500, blank=True)
    source_file_key = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "courses"
        ordering = ["-created_at"]


class Subtopic(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="subtopics")
    title = models.CharField(max_length=500)
    difficulty = models.CharField(max_length=20, default="Intermediate")
    order = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default="pending")
    content_key = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "subtopics"
        ordering = ["order"]
        unique_together = [("course", "order")]


class CourseChunk(models.Model):
    # No FK to Course — loose coupling so embeddings module is independent
    course_id = models.IntegerField(db_index=True)
    subtopic_order = models.PositiveIntegerField()
    chunk_index = models.IntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=768)  # Gemini text-embedding-004

    class Meta:
        db_table = "course_chunks"
        indexes = [
            models.Index(fields=["course_id", "subtopic_order"]),
        ]


class TaskRecord(models.Model):
    task_id = models.CharField(max_length=36, primary_key=True)
    task_type = models.CharField(max_length=50)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, default="running")
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task_records"
