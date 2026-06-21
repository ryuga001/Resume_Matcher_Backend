class PromptBuilder:
    @staticmethod
    def build(chunks,job_description):
        context = "\n\n".join([
            chunk["text"]
            for chunk in chunks
        ])

        return f""" You are an expert ATS and resume reviewer Resume Context: {context} Job Description: {job_description} Analyze the resume against the job description Return JSON ONLY in this format: {{"atsScore": 0, "matchingSkills":[], "missingSkills":[], "recommendations":[], "summary":""}} Rules: -ATS score between 0 and 100 - Missing skills should come from job description -Recommendataions should be actionable -Summary should be concise """