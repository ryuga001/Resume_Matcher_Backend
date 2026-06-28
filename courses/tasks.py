from celery import shared_task

from common.gemini import GeminiService
from common.embeddings import EmbeddingService
from common.mongodb.client import MongoDBClient
from courses.repository import CourseRepository


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_subtopic_content_task(self, course_id: str, subtopic_order: int):
    """
    Worker task: generate content for a single subtopic, upload to S3,
    embed chunks into MongoDB, and update subtopic status.
    """
    repo = CourseRepository()

    # Mark as generating
    repo.update_subtopic_field(course_id, subtopic_order, {"status": "generating"})

    try:
        course = repo.get_by_id(course_id)
        if not course:
            raise ValueError(f"Course {course_id} not found.")

        subtopic = repo.get_subtopic(course_id, subtopic_order)
        if not subtopic:
            raise ValueError(f"Subtopic order={subtopic_order} not found in course {course_id}.")

        source_key = course.get("sourceFileKey", "")
        if not source_key:
            raise ValueError("Course has no source file.")

        gemini = GeminiService()
        content, s3_key = gemini.generate_subtopic_content(
            source_key=source_key,
            topic=course["topic"],
            subtopic_title=subtopic["title"],
            difficulty=subtopic.get("difficulty", "Intermediate"),
        )

        # Embed into MongoDB for RAG
        db = MongoDBClient.get_db()
        EmbeddingService().index_content(db, course_id, subtopic_order, content)

        # Mark done
        repo.update_subtopic_field(course_id, subtopic_order, {
            "status":     "done",
            "contentKey": s3_key,
        })

    except Exception as exc:
        repo.update_subtopic_field(course_id, subtopic_order, {"status": "error"})
        raise self.retry(exc=exc)


@shared_task
def generate_course_content(course_id: str):
    """
    Orchestrator task: fan-out one generate_subtopic_content_task per subtopic.
    Marks all subtopics as pending before dispatching.
    """
    repo = CourseRepository()
    course = repo.get_by_id(course_id)
    if not course:
        return {"error": f"Course {course_id} not found."}

    subtopics = course.get("subtopics", [])
    if not subtopics:
        return {"error": "No subtopics to generate content for."}

    # Reset all to pending
    for s in subtopics:
        repo.update_subtopic_field(course_id, s["order"], {
            "status":     "pending",
            "contentKey": "",
        })

    # Dispatch one task per subtopic — stagger by 15s to stay under free-tier rate limit (5 req/min)
    task_ids = []
    for i, s in enumerate(subtopics):
        result = generate_subtopic_content_task.apply_async(
            args=[course_id, s["order"]],
            countdown=i * 15,  # 0s, 15s, 30s, 45s … — max 4/min
        )
        task_ids.append(result.id)

    return {"dispatched": len(task_ids), "taskIds": task_ids}
