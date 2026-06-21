import json
from analysis.service.retrieval_service import RetrievalService
from analysis.service.prompt_builder import PromptBuilder
from common.ai.llm_service import LLMService

class AnalysisService:

    @staticmethod
    def analyze(resume_id, job_description):
        chunks = RetrievalService().retrieve(resume_id=resume_id,job_description=job_description,top_k=5)
        prompt = PromptBuilder().build(chunks,job_description)
        result = LLMService().generate(prompt)

        try:
            return json.loads(result)
        except Exception:
            return {
                "rawResponse":result
            }