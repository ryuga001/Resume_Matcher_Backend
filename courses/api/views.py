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
    """POST — stream source file from S3, run Gemini agent, return draft list (not saved)."""

    @require_role("SUPER_ADMIN")
    def post(self, request, course_id):
        course = CourseRepository().get_by_id(course_id)
        if not course:
            return Response({"error": "Course not found."}, status=404)

        source_key = course.get("sourceFileKey", "")
        if not source_key:
            return Response({"error": "This course has no source file."}, status=400)

        try:
            subtopics = GeminiService().generate_subtopics(source_key, course["topic"])
        except (ValueError, RuntimeError) as exc:
            return Response({"error": str(exc)}, status=422)

        return Response({"subtopics": subtopics})


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
