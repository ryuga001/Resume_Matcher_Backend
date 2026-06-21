from datetime import datetime, timezone
from bson import ObjectId
from common.mongodb.client import MongoDBClient


class AnalysisRepository:
    def __init__(self):
        self.db = MongoDBClient.get_db()
        self.collection = self.db["analyses"]

    def save(self, user_id: str, resume_id: str, resume_name: str, job_description: str, result: dict) -> str:
        doc = {
            "userId": user_id,
            "resumeId": resume_id,
            "resumeName": resume_name,
            "jobDescription": job_description[:500],
            "result": result,
            "createdAt": datetime.now(timezone.utc),
        }
        inserted = self.collection.insert_one(doc)
        return str(inserted.inserted_id)

    def get_history(self, user_id: str, limit: int = 20):
        cursor = self.collection.find(
            {"userId": user_id},
            {"result": 1, "resumeName": 1, "jobDescription": 1, "createdAt": 1, "resumeId": 1}
        ).sort("createdAt", -1).limit(limit)
        return list(cursor)

    def get_by_id(self, analysis_id: str, user_id: str):
        return self.collection.find_one({"_id": ObjectId(analysis_id), "userId": user_id})
