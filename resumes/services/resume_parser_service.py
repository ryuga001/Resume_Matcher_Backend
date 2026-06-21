import fitz

class ResumeParserService:

    @staticmethod
    def extract_text_from_pdf(file_path) -> str:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text