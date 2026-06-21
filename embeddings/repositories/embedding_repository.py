from common.mongodb.client import MongoDBClient


class EmbeddingRepository:
    def __init__(self):
        self.collection = MongoDBClient.get_db()["resume_chunks"]

    def save_many(self, documents: list):
        self.collection.insert_many(documents)

    def find_by_resume_id(self, resume_id: str):
        return list(self.collection.find({"resumeId": resume_id}, {"_id": 0}))

    def vector_search(self, resume_id: str, query_embedding: list, limit: int = 5):
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "resume_vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": limit,
                    "filter": {"resumeId": resume_id},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "resumeId": 1,
                    "chunkIndex": 1,
                    "text": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        return list(self.collection.aggregate(pipeline))
