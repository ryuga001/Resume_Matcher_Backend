from bson import ObjectId
from common.mongodb.client import MongoDBClient


class UserRepository:
    def __init__(self):
        self.db = MongoDBClient.get_db()
        self.collection = self.db["users"]
        self.collection.create_index("email", unique=True)

    def create_user(self, email: str, hashed_password: str, name: str) -> str:
        doc = {"email": email, "password": hashed_password, "name": name, "usesLeft": 10}
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def find_by_email(self, email: str):
        return self.collection.find_one({"email": email})

    def find_by_id(self, user_id: str):
        return self.collection.find_one({"_id": ObjectId(user_id)})

    def decrement_uses(self, user_id: str) -> int:
        result = self.collection.find_one_and_update(
            {"_id": ObjectId(user_id), "usesLeft": {"$gt": 0}},
            {"$inc": {"usesLeft": -1}},
            return_document=True,
        )
        if result is None:
            return 0
        return result.get("usesLeft", 0)

    def get_uses_left(self, user_id: str) -> int:
        doc = self.collection.find_one({"_id": ObjectId(user_id)}, {"usesLeft": 1})
        if not doc:
            return 0
        return doc.get("usesLeft", 0)
