import re
import time

from celery import shared_task

from common.gemini import GeminiService
from common.embeddings import EmbeddingService
from common.mongodb.client import MongoDBClient
from courses.repository import CourseRepository


def _retry_delay_seconds(err_msg: str, default: int = 65) -> int:
    """Parse retry_delay.seconds out of a Gemini 429 error string."""
    m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', err_msg)
    return int(m.group(1)) + 5 if m else default


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_subtopics_task(self, course_id: str) -> list:
    """Async subtopic generation — streams PDF from S3, calls Gemini, returns list."""
    from courses.repository import CourseRepository
    from common.gemini import GeminiService

    course = CourseRepository().get_by_id(course_id)
    if not course:
        raise ValueError(f"Course {course_id} not found.")
    source_key = course.get("sourceFileKey", "")
    if not source_key:
        raise ValueError("Course has no source file.")
    try:
        return GeminiService().generate_subtopics(source_key, course["topic"])
    except Exception as exc:
        raise self.retry(exc=exc)


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

        # Embed into MongoDB for RAG (soft-fail — don't block content on embed errors)
        try:
            db = MongoDBClient.get_db()
            EmbeddingService().index_content(db, course_id, subtopic_order, content)
        except Exception as embed_exc:
            print(f"[embed] warning: {embed_exc}")

        # Mark done
        repo.update_subtopic_field(course_id, subtopic_order, {
            "status":     "done",
            "contentKey": s3_key,
        })

    except Exception as exc:
        if "429" in str(exc):
            repo.update_subtopic_field(course_id, subtopic_order, {"status": "pending"})
        else:
            repo.update_subtopic_field(course_id, subtopic_order, {"status": "error"})
        raise self.retry(exc=exc)


@shared_task
def generate_course_content(course_id: str):
    """
    Orchestrator: process subtopics one at a time in sequence.
    Stays within Gemini free-tier rate limit naturally — no stagger needed.
    """
    repo    = CourseRepository()
    course  = repo.get_by_id(course_id)
    if not course:
        return {"error": f"Course {course_id} not found."}

    subtopics = course.get("subtopics", [])
    if not subtopics:
        return {"error": "No subtopics to generate content for."}

    # Reset all to pending upfront so the UI shows correct state immediately
    for s in subtopics:
        repo.update_subtopic_field(course_id, s["order"], {"status": "pending", "contentKey": ""})

    source_key = course.get("sourceFileKey", "")
    gemini     = GeminiService()
    done       = 0
    max_attempts = 6

    for s in subtopics:
        order = s["order"]

        for attempt in range(max_attempts):
            repo.update_subtopic_field(course_id, order, {"status": "generating"})
            try:
                content, s3_key = gemini.generate_subtopic_content(
                    source_key=source_key,
                    topic=course["topic"],
                    subtopic_title=s["title"],
                    difficulty=s.get("difficulty", "Intermediate"),
                )
                try:
                    db = MongoDBClient.get_db()
                    EmbeddingService().index_content(db, course_id, order, content)
                except Exception as embed_exc:
                    print(f"[embed] warning: {embed_exc}")
                repo.update_subtopic_field(course_id, order, {"status": "done", "contentKey": s3_key})
                done += 1
                break  # success — move to next subtopic

            except RuntimeError as exc:
                err = str(exc)
                if "429" in err and attempt < max_attempts - 1:
                    delay = _retry_delay_seconds(err)
                    repo.update_subtopic_field(course_id, order, {"status": "pending"})
                    time.sleep(delay)   # respect Gemini's retry-after
                    continue
                repo.update_subtopic_field(course_id, order, {"status": "error"})
                break

            except Exception:
                repo.update_subtopic_field(course_id, order, {"status": "error"})
                break

    return {"done": done, "total": len(subtopics)}
