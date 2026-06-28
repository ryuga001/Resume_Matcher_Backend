import json

from rest_framework.views import APIView
from rest_framework.response import Response

from common.s3 import S3Service
from common.gemini import GeminiService
from users.auth import require_auth, require_role
from courses.repository import CourseRepository, VALID_STATUSES

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
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=500)

        return Response(result)


class CourseListView(APIView):
    @require_auth
    def get(self, request):
        search   = request.query_params.get("search",   "")
        category = request.query_params.get("category", "")
        status   = request.query_params.get("status",   "")
        courses  = CourseRepository().list_courses(search=search, category=category, status=status)
        return Response([_enrich(c) for c in courses])

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

        # Collect keys before deleting the DB record
        keys = [
            course.get("thumbnailKey")  or course.get("thumbnailUrl",  ""),
            course.get("sourceFileKey") or course.get("sourceFileUrl", ""),
        ]

        repo.delete(course_id)
        s3.delete_many(keys)

        return Response({"ok": True})


class SubtopicsGenerateView(APIView):
    """POST — enqueue async subtopic generation, return taskId immediately."""

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id):
        from courses.tasks import generate_subtopics_task

        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)

        source_key = course.get("sourceFileKey", "")
        if not source_key:
            return Response({"error": "This course has no source file."}, status=400)

        result = generate_subtopics_task.delay(course_id)
        return Response({"taskId": result.id})


class SubtopicsTaskStatusView(APIView):
    """GET — poll Celery task result for subtopic generation."""

    @require_role("SUPER_ADMIN")
    def get(self, request, course_id, task_id):
        from celery.result import AsyncResult
        result = AsyncResult(task_id)

        if result.state == "SUCCESS":
            return Response({"status": "done", "subtopics": result.result})

        if result.state == "FAILURE":
            err = str(result.result) if result.result else "Generation failed."
            err = err.splitlines()[0]
            return Response({"status": "error", "error": err})

        return Response({"status": "running"})


class SubtopicsView(APIView):
    """PUT — save the (possibly edited) subtopics list to MongoDB."""

    @require_role("SUPER_ADMIN")
    def put(self, request, course_id):
        subtopics = request.data.get("subtopics")
        if not isinstance(subtopics, list):
            return Response({"error": "subtopics must be an array."}, status=400)

        # Normalise & re-number
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
    """POST — enqueue Celery tasks to generate content for all subtopics."""

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id):
        from courses.tasks import generate_course_content
        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)
        if not course.get("subtopics"):
            return Response({"error": "No subtopics — generate subtopics first."}, status=400)
        result = generate_course_content.delay(course_id)
        return Response({"taskId": result.id, "queued": True})


class ContentStatusView(APIView):
    """GET — return subtopic-level generation statuses."""

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
    """GET — fetch generated content JSON. PUT — admin saves edited content."""

    @require_auth
    def get(self, request, course_id, order):
        order = int(order)
        subtopic = CourseRepository().get_subtopic(course_id, order)
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)
        content_key = subtopic.get("contentKey", "")
        if not content_key or subtopic.get("status") != "done":
            return Response({"error": "Content not yet generated."}, status=404)
        try:
            raw = s3.get_text(content_key)
            content = json.loads(raw)
        except Exception:
            return Response({"error": "Could not load content from storage."}, status=500)
        return Response({"content": content, "subtopic": subtopic})

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id, order):
        """Enqueue generation for a single subtopic."""
        from courses.tasks import generate_subtopic_content_task
        order = int(order)
        repo = CourseRepository()
        subtopic = repo.get_subtopic(course_id, order)
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)
        # Mark synchronously so the UI sees "generating" on the next poll
        repo.update_subtopic_field(course_id, order, {"status": "generating", "contentKey": ""})
        generate_subtopic_content_task.delay(course_id, order)
        return Response({"queued": True})

    @require_role("SUPER_ADMIN")
    def put(self, request, course_id, order):
        order = int(order)
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

        # Re-embed updated content
        from common.embeddings import EmbeddingService
        from common.mongodb.client import MongoDBClient
        try:
            EmbeddingService().index_content(MongoDBClient.get_db(), course_id, order, content)
        except Exception:
            pass  # Don't fail the save if re-embedding fails

        return Response({"ok": True})


class SubtopicChatView(APIView):
    """POST — RAG-based chat for a specific subtopic."""

    @require_auth
    def post(self, request, course_id, order):
        message = request.data.get("message", "").strip()
        history = request.data.get("history", [])

        if not message:
            return Response({"error": "message is required."}, status=400)

        repo   = CourseRepository()
        course = repo.get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)

        subtopic = repo.get_subtopic(course_id, int(order))
        if not subtopic:
            return Response({"error": "Subtopic not found."}, status=404)

        content_key = subtopic.get("contentKey", "")
        if not content_key:
            return Response({"error": "Content not generated yet for this subtopic."}, status=400)

        # Load content from S3 and build context text
        try:
            raw     = s3.get_text(content_key)
            content = json.loads(raw)
        except Exception:
            return Response({"error": "Could not load subtopic content."}, status=500)

        context_parts: list[str] = []
        if overview := content.get("overview"):
            context_parts.append(f"Overview:\n{overview}")
        for t in content.get("theory", []):
            context_parts.append(f"{t.get('heading', '')}:\n{t.get('body', '')}")
        if kp := content.get("key_points"):
            context_parts.append("Key Points:\n" + "\n".join(f"- {k}" for k in kp))
        context_text = "\n\n".join(context_parts)

        # Narrow context via RAG if embeddings exist
        try:
            from common.embeddings import EmbeddingService
            from common.mongodb.client import MongoDBClient
            chunks = EmbeddingService().search(MongoDBClient.get_db(), course_id, message, top_k=5)
            if chunks:
                context_text = "\n\n---\n\n".join(c["text"] for c in chunks)
        except Exception:
            pass  # Fall back to full content context

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
