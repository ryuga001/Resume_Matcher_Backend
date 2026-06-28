import threading
from pathlib import Path

from resumes.services.resume_parser_service import ResumeParserService
from resumes.services.skill_extraction_service import SkillExtrationService
from resumes.repositories.resume_repositories import ResumeRepository
from embeddings.service.indexing_service import IndexingService

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "resumes"


class ResumeService:
    """Orchestrates resume upload: parse → extract skills → persist → async index."""

    def __init__(self) -> None:
        self._repository = ResumeRepository()

    def process_resume(self, uploaded_file, user_id: str) -> str:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / uploaded_file.name

        with open(path, "wb+") as fh:
            for chunk in uploaded_file.chunks():
                fh.write(chunk)

        content = ResumeParserService.extract_text_from_pdf(path)
        skills  = SkillExtrationService.extract(content)

        resume_id = self._repository.save_resume({
            "userId":    user_id,
            "fileName":  uploaded_file.name,
            "resumeText": content,
            "skills":    skills,
        })

        threading.Thread(
            target=self._index_async,
            args=(resume_id, content),
            daemon=True,
        ).start()

        return resume_id

    def _index_async(self, resume_id: str, content: str) -> None:
        try:
            IndexingService().index_resume(resume_id, content)
            self._repository.set_index_status(resume_id, "ready")
        except Exception:
            self._repository.set_index_status(resume_id, "error")
