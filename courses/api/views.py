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
