from bson import ObjectId

from common.mongodb.client import MongoDBClient

class ResumeRepository:
    def __init__(self):
        self.db = MongoDBClient.get_db()
        self.collection = self.db['resumes']

    def save_resume(self, resume_data):
        result = self.collection.insert_one(resume_data)
        return str(result.inserted_id)

    def get_resume_by_id(self, resume_id):
        return self.collection.find_one({"_id": ObjectId(resume_id)})

    def update_resume(self, resume_id, updated_data):
        result = self.collection.update_one({"_id": resume_id}, {"$set": updated_data})
        return result.modified_count > 0

    def delete_resume(self, resume_id):
        result = self.collection.delete_one({"_id": resume_id})
        return result.deleted_count > 0

    def get_all_resumes(self):
        return list(self.collection.find({}, {"_id": 1, "fileName": 1}))