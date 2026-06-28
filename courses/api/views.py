import json
import uuid

from rest_framework.views import APIView
from rest_framework.response import Response

from common.s3 import S3Service
from common.gemini import GeminiService
from common.rabbitmq import publish
from users.auth import require_auth, require_role
from courses.repository import CourseRepository, VALID_STATUSES
from courses.models import TaskRecord

s3 = S3Service()


def _enrich(course: dict) -> dict:
    """Replace stored S3 keys with short-lived presigned GET URLs."""
    course["thumbnailUrl"]  = s3.presign_get(course.pop("thumbnailKey",  ""))
    course["sourceFileUrl"] = s3.presign_get(course.pop("sourceFileKey", ""))
    return course


class PresignView(APIView):
    @require_role("SUPER_ADMIN")
    def post(self, request):
        filename     = request.data.get("filename", "").strip()
        content_type = request.data.get("contentType", "application/octet-stream")
        upload_type  = request.data.get("uploadType", "source")

        if upload_type not in ("source", "thumbnail"):
            return Response({"error": "uploadType must be 'source' or 'thumbnail'."}, status=400)
        try:
            result = s3.presign_put(filename, content_type, f"courses/{upload_type}")
        except (ValueError, RuntimeError) as exc:
            return Response({"error": str(exc)}, status=400 if isinstance(exc, ValueError) else 500)
        return Response(result)


class CourseListView(APIView):
    @require_auth
    def get(self, request):
        search   = request.query_params.get("search",   "")
        category = request.query_params.get("category", "")
        status   = request.query_params.get("status",   "")
        return Response([_enrich(c) for c in CourseRepository().list_courses(search=search, category=category, status=status)])

    @require_role("SUPER_ADMIN")
    def post(self, request):
        topic           = request.data.get("topic", "").strip()
        categories      = request.data.get("categories", [])
        status          = request.data.get("status", "Not Available")
        thumbnail_key   = request.data.get("thumbnailKey", "")
        source_file_key = request.data.get("sourceFileKey", "")

        if not topic:
            return Response({"error": "topic is required."}, status=400)
        if not isinstance(categories, list):
            return Response({"error": "categories must be an array."}, status=400)
        if status not in VALID_STATUSES:
            return Response({"error": f"status must be one of {VALID_STATUSES}."}, status=400)
        try:
            course = CourseRepository().create(topic, categories, status, thumbnail_key, source_file_key)
            return Response(_enrich(course), status=201)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)


class CourseDetailView(APIView):
    @require_auth
    def get(self, request, course_id):
        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        return Response(_enrich(course))

    @require_role("SUPER_ADMIN")
    def patch(self, request, course_id):
        allowed = {"topic", "categories", "status", "thumbnailKey", "sourceFileKey"}
        updates = {k: v for k, v in request.data.items() if k in allowed}
        if not updates:
            return Response({"error": "No valid fields to update."}, status=400)
        try:
            course = CourseRepository().update(course_id, updates)
            if not course:
                return Response({"error": "Course not found."}, status=404)
            return Response(_enrich(course))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

    @require_role("SUPER_ADMIN")
    def delete(self, request, course_id):
        repo   = CourseRepository()
        course = repo.get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        keys = [course.get("thumbnailKey", ""), course.get("sourceFileKey", "")]
        repo.delete(course_id)
        s3.delete_many(keys)
        return Response({"ok": True})


class SubtopicsGenerateView(APIView):
    """POST — enqueue async subtopic generation via RabbitMQ, return taskId."""

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id):
        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        if not course.get("sourceFileKey"):
            return Response({"error": "This course has no source file."}, status=400)

        task_id = str(uuid.uuid4())
        record = TaskRecord.objects.create(task_id=task_id, task_type="subtopics", course_id=int(course_id))
        try:
            publish("subtopics_generation", {"task_id": task_id, "course_id": str(course_id)})
        except Exception as exc:
            record.delete()
            return Response({"error": f"Message broker unavailable: {exc}"}, status=503)
        return Response({"taskId": task_id})


class SubtopicsTaskStatusView(APIView):
    """GET — poll task record for subtopic generation progress."""

    @require_role("SUPER_ADMIN")
    def get(self, request, course_id, task_id):
        try:
            record = TaskRecord.objects.get(task_id=task_id)
        except TaskRecord.DoesNotExist:
            # Always 200 so RTK Query routes the body to `data`, not `error`
            return Response({"status": "error", "error": "Task not found."})

        if record.status == "done":
            return Response({"status": "done", "subtopics": record.result})
        if record.status == "error":
            return Response({"status": "error", "error": record.error_message or "Generation failed."})
        return Response({"status": "running"})


class SubtopicsView(APIView):
    """PUT — save the edited subtopics list."""

    @require_role("SUPER_ADMIN")
    def put(self, request, course_id):
        subtopics = request.data.get("subtopics")
        if not isinstance(subtopics, list):
            return Response({"error": "subtopics must be an array."}, status=400)

        valid_difficulties = {"Beginner", "Intermediate", "Advanced"}
        cleaned = []
        for i, s in enumerate(subtopics):
            title = str(s.get("title", "")).strip()
            if not title:
                continue
            difficulty = s.get("difficulty", "Intermediate")
            if difficulty not in valid_difficulties:
                difficulty = "Intermediate"
            cleaned.append({"title": title, "difficulty": difficulty, "order": i + 1})

        course = CourseRepository().save_subtopics(course_id, cleaned)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        return Response({"subtopics": course.get("subtopics", [])})


class ContentGenerateView(APIView):
    """POST — enqueue bulk content generation for all subtopics."""

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id):
        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        if not course.get("subtopics"):
            return Response({"error": "No subtopics — generate subtopics first."}, status=400)
        try:
            publish("bulk_content_generation", {"course_id": str(course_id)})
        except Exception as exc:
            return Response({"error": f"Message broker unavailable: {exc}"}, status=503)
        return Response({"queued": True})


class ContentStatusView(APIView):
    """GET — return per-subtopic generation statuses."""

    @require_auth
    def get(self, request, course_id):
        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        statuses = [
            {"order": s["order"], "status": s.get("status", "pending")}
            for s in course.get("subtopics", [])
        ]
        return Response({"statuses": statuses})


class SubtopicContentView(APIView):
    """GET — fetch content JSON. POST — enqueue single-subtopic gen. PUT — save edits."""

    @require_auth
    def get(self, request, course_id, order):
        repo     = CourseRepository()
        subtopic = repo.get_subtopic(course_id, order)
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)
        content_key = subtopic.get("contentKey", "")
        if not content_key or subtopic.get("status") != "done":
            return Response({"error": "Content not yet generated."}, status=404)
        try:
            content = json.loads(s3.get_text(content_key))
        except Exception:
            return Response({"error": "Could not load content from storage."}, status=500)
        return Response({"content": content, "subtopic": subtopic})

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id, order):
        repo     = CourseRepository()
        subtopic = repo.get_subtopic(course_id, order)
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)
        # Mark generating synchronously so the next poll shows the right status
        repo.update_subtopic_field(course_id, order, {"status": "generating", "contentKey": ""})
        try:
            publish("content_generation", {"course_id": str(course_id), "order": order})
        except Exception as exc:
            repo.update_subtopic_field(course_id, order, {"status": "error"})
            return Response({"error": f"Message broker unavailable: {exc}"}, status=503)
        return Response({"queued": True})

    @require_role("SUPER_ADMIN")
    def put(self, request, course_id, order):
        content = request.data.get("content")
        if not isinstance(content, dict):
            return Response({"error": "content must be a JSON object."}, status=400)

        subtopic = CourseRepository().get_subtopic(course_id, order)
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)

        content_key = subtopic.get("contentKey", "")
        if not content_key:
            return Response({"error": "No content key — content was never generated."}, status=400)

        try:
            s3.put_text(content_key, json.dumps(content, ensure_ascii=False), "application/json")
        except Exception as exc:
            return Response({"error": f"Could not save content: {exc}"}, status=500)

        try:
            from common.embeddings import EmbeddingService
            EmbeddingService().index_content(str(course_id), order, content)
        except Exception:
            pass

        return Response({"ok": True})


class SubtopicChatView(APIView):
    """POST — RAG-based chat for a specific subtopic."""

    @require_auth
    def post(self, request, course_id, order):
        message = request.data.get("message", "").strip()
        history = request.data.get("history", [])
        if not message:
            return Response({"error": "message is required."}, status=400)

        repo     = CourseRepository()
        course   = repo.get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)

        subtopic = repo.get_subtopic(course_id, int(order))
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)

        content_key = subtopic.get("contentKey", "")
        if not content_key:
            return Response({"error": "Content not generated yet for this subtopic."}, status=400)

        try:
            content = json.loads(s3.get_text(content_key))
        except Exception:
            return Response({"error": "Could not load subtopic content."}, status=500)

        # Build full-content context as fallback
        parts: list[str] = []
        if ov := content.get("overview"):
            parts.append(f"Overview:\n{ov}")
        for t in content.get("theory", []):
            parts.append(f"{t.get('heading', '')}:\n{t.get('body', '')}")
        if kp := content.get("key_points"):
            parts.append("Key Points:\n" + "\n".join(f"- {k}" for k in kp))
        context_text = "\n\n".join(parts)

        # Narrow via pgvector RAG if embeddings exist
        try:
            from common.embeddings import EmbeddingService
            chunks = EmbeddingService().search(str(course_id), message, top_k=5)
            if chunks:
                context_text = "\n\n---\n\n".join(c["text"] for c in chunks)
        except Exception:
            pass

        try:
            reply = GeminiService().chat_subtopic(
                topic=course["topic"],
                subtopic_title=subtopic["title"],
                context=context_text,
                history=history,
                message=message,
            )
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=503)

        return Response({"reply": reply})
