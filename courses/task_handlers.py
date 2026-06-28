"""
Pure task logic — no Celery, no RabbitMQ. Called by worker scripts.
Keeps business rules in one place, testable without a message broker.
"""
import re
import time

from common.gemini import GeminiService
from common.embeddings import EmbeddingService
from courses.repository import CourseRepository
from courses.models import TaskRecord


def _retry_delay_seconds(err_msg: str, default: int = 65) -> int:
    m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', err_msg)
    return int(m.group(1)) + 5 if m else default


# ── Subtopic generation ───────────────────────────────────────────────────────

def handle_generate_subtopics(task_id: str, course_id: str) -> None:
    """
    Generate subtopics for a course and persist the result.
    Updates TaskRecord status on completion or failure.
    """
    repo = CourseRepository()
    try:
        course = repo.get_by_id(course_id)
        if not course:
            raise ValueError(f"Course {course_id} not found.")
        source_key = course.get("sourceFileKey", "")
        if not source_key:
            raise ValueError("Course has no source file.")

        subtopics = GeminiService().generate_subtopics(source_key, course["topic"])
        TaskRecord.objects.filter(task_id=task_id).update(
            status="done",
            result=subtopics,
        )
    except Exception as exc:
        TaskRecord.objects.filter(task_id=task_id).update(
            status="error",
            error_message=str(exc)[:2000],
        )
        raise


# ── Single subtopic content generation ───────────────────────────────────────

def handle_generate_subtopic_content(course_id: str, order: int) -> None:
    """
    Generate, upload, and embed content for one subtopic.
    Updates subtopic status directly; never raises (marks error on failure).
    """
    repo = CourseRepository()
    repo.update_subtopic_field(course_id, order, {"status": "generating"})

    max_attempts = 6
    for attempt in range(max_attempts):
        try:
            course = repo.get_by_id(course_id)
            if not course:
                raise ValueError(f"Course {course_id} not found.")
            subtopic = repo.get_subtopic(course_id, order)
            if not subtopic:
                raise ValueError(f"Subtopic order={order} not found.")

            content, s3_key = GeminiService().generate_subtopic_content(
                source_key=course["sourceFileKey"],
                topic=course["topic"],
                subtopic_title=subtopic["title"],
                difficulty=subtopic.get("difficulty", "Intermediate"),
            )

            try:
                EmbeddingService().index_content(course_id, order, content)
            except Exception as embed_exc:
                print(f"[embed] warning: {embed_exc}")

            repo.update_subtopic_field(course_id, order, {"status": "done", "contentKey": s3_key})
            return  # success

        except RuntimeError as exc:
            err = str(exc)
            if "429" in err and attempt < max_attempts - 1:
                delay = _retry_delay_seconds(err)
                repo.update_subtopic_field(course_id, order, {"status": "pending"})
                time.sleep(delay)
                repo.update_subtopic_field(course_id, order, {"status": "generating"})
                continue
            repo.update_subtopic_field(course_id, order, {"status": "error"})
            return

        except Exception:
            repo.update_subtopic_field(course_id, order, {"status": "error"})
            return


# ── Bulk content generation (all subtopics sequentially) ─────────────────────

def handle_generate_all_content(course_id: str) -> dict:
    """
    Process every subtopic in a course one by one.
    Natural sequential throttling respects Gemini free-tier limits.
    """
    repo = CourseRepository()
    course = repo.get_by_id(course_id)
    if not course:
        return {"error": f"Course {course_id} not found."}

    subtopics = course.get("subtopics", [])
    if not subtopics:
        return {"error": "No subtopics to generate."}

    for s in subtopics:
        repo.update_subtopic_field(course_id, s["order"], {"status": "pending", "contentKey": ""})

    done = 0
    for s in subtopics:
        handle_generate_subtopic_content(course_id, s["order"])
        if repo.get_subtopic(course_id, s["order"]).get("status") == "done":
            done += 1

    return {"done": done, "total": len(subtopics)}
