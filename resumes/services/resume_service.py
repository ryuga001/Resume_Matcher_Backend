import os
from pathlib import Path

from resumes.services.resume_parser_service import ResumeParserService
from resumes.services.skill_extraction_service import SkillExtrationService
from resumes.repositories.resume_repositories import ResumeRepository
from embeddings.service.indexing_service import IndexingService

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "resumes"

class ResumeService:

    def __init__(self):
        self.repository = ResumeRepository()

    def process_resume(self, uploaded_file) -> str:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / uploaded_file.name

        with open(path, "wb+") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        
        content = ResumeParserService.extract_text_from_pdf(path)
        skills = SkillExtrationService.extract(content)
        document = {
            "fileName" : uploaded_file.name,
            "resumeText": content,
            "skills" : skills
        }

        resume_id = self.repository.save_resume(document)

        indexingService = IndexingService()
        
        indexingService.index_resume(resume_id, content)

        return resume_id