import os
from google import genai
from google.genai import types

class LLMService:
    _client = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            cls._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return cls._client

    @classmethod
    def generate(cls, prompt: str) -> str:
        response = cls._get_client().models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return response.text
