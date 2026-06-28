import os
from google import genai
from google.genai import types


class LLMService:
    def generate(self, prompt: str) -> str:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return client.models.generate_content(
            model=os.getenv("GEMINI_MODEL"),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        ).text
