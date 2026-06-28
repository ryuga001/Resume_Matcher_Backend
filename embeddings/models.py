from django.db import models
from pgvector.django import VectorField


class ResumeChunk(models.Model):
    # Raw integer FK — no ORM relation to keep embeddings app self-contained
    resume_id = models.IntegerField(db_index=True)
    chunk_index = models.IntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=384)  # all-MiniLM-L6-v2

    class Meta:
        db_table = "resume_chunks"
        indexes = [
            models.Index(fields=["resume_id"]),
        ]
