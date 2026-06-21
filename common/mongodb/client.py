import os
from pymongo import MongoClient


class MongoDBClient:
    _client = None
    _db = None

    @classmethod
    def get_db(cls):
        if cls._db is None:
            cls._client = MongoClient(os.getenv("MONGO_URI"))
            cls._db = cls._client[os.getenv("MONGO_DB_NAME")]
        return cls._db
