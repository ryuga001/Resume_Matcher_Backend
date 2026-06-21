import threading
from datetime import datetime, timezone
from pathlib import Path

from resumes.services.resume_parser_service import ResumeParserService
from resumes.services.skill_extraction_service import SkillExtrationService
from resumes.repositories.resume_repositories import ResumeRepository
from embeddings.service.indexing_service import IndexingService

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "resumes"


class ResumeService:
    def __init__(self):
        self.repository = ResumeRepository()

    def process_resume(self, uploaded_file, user_id: str) -> str:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / uploaded_file.name

        with open(path, "wb+") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        content = ResumeParserService.extract_text_from_pdf(path)
        skills = SkillExtrationService.extract(content)

        document = {
            "userId": user_id,
            "fileName": uploaded_file.name,
            "resumeText": content,
            "skills": skills,
            "uploadedAt": datetime.now(timezone.utc),
            "indexStatus": "processing",
        }

        resume_id = self.repository.save_resume(document)

        # Index in background thread so upload returns fast
        thread = threading.Thread(
            target=self._index_async,
            args=(resume_id, content),
            daemon=True,
        )
        thread.start()

        return resume_id

    def _index_async(self, resume_id: str, content: str):
        try:
            IndexingService().index_resume(resume_id, content)
            self.repository.set_index_status(resume_id, "ready")
        except Exception:
            self.repository.set_index_status(resume_id, "error")
