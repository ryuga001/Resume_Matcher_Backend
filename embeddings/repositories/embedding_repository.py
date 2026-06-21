from common.mongodb.client import MongoDBClient

class EmbeddingRepository:

    def __init__(self):
        db = MongoDBClient.get_db()
        self.collection = db['resume_chunks']

    
    def save_many(self,documents):
        self.collection.insert_many(documents)

    def find_by_resume_id(self,resume_id):
        return list(self.collection.find({"resumeId" : resume_id},{"_id":0}))