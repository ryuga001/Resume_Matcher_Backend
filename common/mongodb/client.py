import os

from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

class MongoDBClient:
    _client = None
    _db = None  

    @classmethod
    def get_client(cls):
        if cls._client is None:
            mongo_uri = os.getenv("MONGO_URI")
            cls._client = MongoClient(mongo_uri)
        return cls._client

    @classmethod
    def get_db(cls):
        if cls._db is None:
            cls._db = cls.get_client()[os.getenv("MONGO_DB_NAME")]
        return cls._db
    
    @classmethod
    def close_client(cls):
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            