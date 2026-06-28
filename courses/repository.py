from __future__ import annotations

from django.db import transaction

from courses.models import Course, Subtopic

VALID_STATUSES = ("Not Available", "Available")


class CourseRepository:
    """Data-access layer for Course and Subtopic. Returns plain dicts throughout."""

    # ── Courses ───────────────────────────────────────────────────────────────

    def list_courses(self, search: str = "", category: str = "", status: str = "") -> list[dict]:
        qs = Course.objects.prefetch_related("subtopics").order_by("-created_at")
        if search:
            qs = qs.filter(topic__icontains=search)
        if category:
            qs = qs.filter(categories__contains=[category])
        if status:
            qs = qs.filter(status=status)
        return [self._serialize_course(c) for c in qs]

    def get_by_id(self, course_id) -> dict | None:
        try:
            c = Course.objects.prefetch_related("subtopics").get(id=int(course_id))
            return self._serialize_course(c)
        except (Course.DoesNotExist, ValueError, TypeError):
            return None

    def create(
        self,
        topic: str,
        categories: list,
        status: str,
        thumbnail_key: str,
        source_file_key: str,
    ) -> dict:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        c = Course.objects.create(
            topic=topic,
            categories=categories,
            status=status,
            thumbnail_key=thumbnail_key,
            source_file_key=source_file_key,
        )
        return self._serialize_course(c)

    def update(self, course_id, updates: dict) -> dict | None:
        field_map = {
            "topic":         "topic",
            "categories":    "categories",
            "status":        "status",
            "thumbnailKey":  "thumbnail_key",
            "sourceFileKey": "source_file_key",
        }
        if "status" in updates and updates["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {updates['status']}")
        orm_updates = {field_map[k]: v for k, v in updates.items() if k in field_map}
        if not orm_updates:
            return self.get_by_id(course_id)
        Course.objects.filter(id=int(course_id)).update(**orm_updates)
        return self.get_by_id(course_id)

    def delete(self, course_id) -> bool:
        deleted, _ = Course.objects.filter(id=int(course_id)).delete()
        return deleted > 0

    # ── Subtopics ─────────────────────────────────────────────────────────────

    def save_subtopics(self, course_id, subtopics: list) -> dict | None:
        try:
            course = Course.objects.prefetch_related("subtopics").get(id=int(course_id))
        except (Course.DoesNotExist, ValueError, TypeError):
            return None

        existing = {s.order: s for s in course.subtopics.all()}

        with transaction.atomic():
            course.subtopics.all().delete()
            Subtopic.objects.bulk_create([
                Subtopic(
                    course=course,
                    title=s["title"],
                    difficulty=s.get("difficulty", "Intermediate"),
                    order=s["order"],
                    status=existing[s["order"]].status if s["order"] in existing else "pending",
                    content_key=existing[s["order"]].content_key if s["order"] in existing else "",
                )
                for s in subtopics
            ])

        return self.get_by_id(course_id)

    def update_subtopic_field(self, course_id, order: int, fields: dict) -> bool:
        field_map = {"status": "status", "contentKey": "content_key"}
        orm_fields = {field_map.get(k, k): v for k, v in fields.items()}
        updated = Subtopic.objects.filter(course_id=int(course_id), order=order).update(**orm_fields)
        return updated > 0

    def get_subtopic(self, course_id, order: int) -> dict | None:
        try:
            s = Subtopic.objects.get(course_id=int(course_id), order=order)
            return self._serialize_subtopic(s)
        except (Subtopic.DoesNotExist, ValueError, TypeError):
            return None

    def get_content_statuses(self, course_id) -> list[dict]:
        return [
            {"order": s.order, "status": s.status}
            for s in Subtopic.objects.filter(course_id=int(course_id)).only("order", "status")
        ]

    # ── Serialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _serialize_course(c: Course) -> dict:
        return {
            "id":            str(c.id),
            "topic":         c.topic,
            "categories":    c.categories,
            "status":        c.status,
            "thumbnailKey":  c.thumbnail_key,
            "sourceFileKey": c.source_file_key,
            "createdAt":     c.created_at.isoformat(),
            "updatedAt":     c.updated_at.isoformat(),
            "subtopics": [
                CourseRepository._serialize_subtopic(s)
                for s in c.subtopics.all()
            ],
        }

    @staticmethod
    def _serialize_subtopic(s: Subtopic) -> dict:
        return {
            "title":      s.title,
            "difficulty": s.difficulty,
            "order":      s.order,
            "status":     s.status,
            "contentKey": s.content_key,
        }
