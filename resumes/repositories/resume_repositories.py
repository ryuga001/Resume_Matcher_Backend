from bson import ObjectId
from common.mongodb.client import MongoDBClient


class ResumeRepository:
    def __init__(self):
        self.db = MongoDBClient.get_db()
        self.collection = self.db["resumes"]

    def save_resume(self, resume_data: dict) -> str:
        result = self.collection.insert_one(resume_data)
        return str(result.inserted_id)

    def get_resume_by_id(self, resume_id: str, user_id: str = None):
        query = {"_id": ObjectId(resume_id)}
        if user_id:
            query["userId"] = user_id
        return self.collection.find_one(query)

    def get_all_resumes(self, user_id: str):
        return list(self.collection.find(
            {"userId": user_id},
            {"_id": 1, "fileName": 1, "uploadedAt": 1, "indexStatus": 1, "skills": 1}
        ))

    def set_index_status(self, resume_id: str, status: str):
        self.collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": {"indexStatus": status}}
        )

    def delete_resume(self, resume_id: str, user_id: str) -> bool:
        result = self.collection.delete_one({"_id": ObjectId(resume_id), "userId": user_id})
        return result.deleted_count > 0
