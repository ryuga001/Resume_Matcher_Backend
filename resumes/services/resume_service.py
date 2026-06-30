import os
import tempfile
import threading
import uuid
from pathlib import Path

from resumes.services.resume_parser_service import ResumeParserService
from resumes.services.skill_extraction_service import SkillExtrationService
from resumes.repositories.resume_repositories import ResumeRepository
from embeddings.service.indexing_service import IndexingService
from common.s3 import S3Service


class ResumeService:
    """Orchestrates resume upload: parse → extract skills → upload to S3 → persist → async index."""

    def __init__(self) -> None:
        self._repository = ResumeRepository()
        self._s3 = S3Service()

    def process_resume(self, uploaded_file, user_id: str) -> str:
        suffix = Path(uploaded_file.name).suffix.lower() or ".pdf"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            content = ResumeParserService.extract_text_from_pdf(tmp_path)
            skills  = SkillExtrationService.extract(content)
            s3_key  = f"resumes/{uuid.uuid4()}{suffix}"
            self._s3.upload_file(tmp_path, s3_key, "application/pdf")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        resume_id = self._repository.save_resume({
            "userId":     user_id,
            "fileName":   uploaded_file.name,
            "resumeText": content,
            "skills":     skills,
            "s3Key":      s3_key,
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
