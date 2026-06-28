from datetime import datetime, timezone
from bson import ObjectId
from common.mongodb.client import MongoDBClient

VALID_STATUSES = ("Not Available", "Available")


class CourseRepository:
    def __init__(self):
        self.db = MongoDBClient.get_db()
        self.collection = self.db["courses"]
        self.collection.create_index("topic")
        self.collection.create_index("categories")
        self.collection.create_index("status")

    def _serialize(self, doc: dict) -> dict:
        doc["id"] = str(doc.pop("_id"))
        return doc

    def list_courses(self, search: str = "", category: str = "", status: str = "") -> list:
        query: dict = {}
        if search:
            query["topic"] = {"$regex": search, "$options": "i"}
        if category:
            query["categories"] = category
        if status:
            query["status"] = status
        docs = self.collection.find(query).sort("createdAt", -1)
        return [self._serialize(d) for d in docs]

    def get_by_id(self, course_id: str) -> dict | None:
        doc = self.collection.find_one({"_id": ObjectId(course_id)})
        return self._serialize(doc) if doc else None

    def create(self, topic: str, categories: list, status: str, thumbnail_key: str, source_file_key: str) -> dict:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "topic": topic,
            "categories": categories,
            "status": status,
            "thumbnailKey": thumbnail_key,
            "sourceFileKey": source_file_key,
            "createdAt": now,
            "updatedAt": now,
        }
        result = self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc.pop("_id", None)
        return doc

    def update(self, course_id: str, updates: dict) -> dict | None:
        if "status" in updates and updates["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {updates['status']}")
        updates["updatedAt"] = datetime.now(timezone.utc).isoformat()
        result = self.collection.find_one_and_update(
            {"_id": ObjectId(course_id)},
            {"$set": updates},
            return_document=True,
        )
        return self._serialize(result) if result else None

    def delete(self, course_id: str) -> bool:
        result = self.collection.delete_one({"_id": ObjectId(course_id)})
        return result.deleted_count > 0
