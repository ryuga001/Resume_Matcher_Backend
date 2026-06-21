KNOWN_SKILLS = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl", "Shell",
    # Web
    "React", "Next.js", "Vue", "Angular", "Svelte", "HTML", "CSS", "Tailwind",
    "Node.js", "Express", "FastAPI", "Flask", "Django", "Ruby on Rails", "Spring Boot",
    "GraphQL", "REST", "WebSockets", "gRPC",
    # Data / AI / ML
    "TensorFlow", "PyTorch", "Keras", "scikit-learn", "Pandas", "NumPy", "Spark",
    "Hadoop", "Kafka", "Airflow", "dbt", "Tableau", "Power BI", "Looker",
    "LangChain", "LlamaIndex", "OpenAI", "Hugging Face", "RAG", "NLP",
    # Databases
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "DynamoDB", "Snowflake", "BigQuery", "SQLite",
    # Cloud / DevOps
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Ansible",
    "CI/CD", "GitHub Actions", "Jenkins", "Linux", "Nginx",
    # Practices / Tools
    "Git", "Agile", "Scrum", "Jira", "Figma", "Microservices", "System Design",
    "API Design", "Unit Testing", "TDD", "Code Review",
]

_LOWER = {s.lower(): s for s in KNOWN_SKILLS}


class SkillExtrationService:
    @staticmethod
    def extract(text: str) -> list:
        lowered = text.lower()
        return [canonical for lower, canonical in _LOWER.items() if lower in lowered]
