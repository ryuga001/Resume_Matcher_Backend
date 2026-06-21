KNOWN_SKILLS = [
    "Python",
    "Java",
    "C++",
    "JavaScript",
    "SQL",
    "HTML",
    "CSS",
    "React",
    "Angular",
    "Node.js",
    "Django",
    "Flask",
    "Ruby on Rails",
    "Swift",
    "Kotlin",
    "Go",
    "PHP",
    "docker",
    "kubernetes",
    "redis"
]


class SkillExtrationService:

    @staticmethod
    def extract(text:str)->str:
        text = text.lower()
        skills = []
        for skill in KNOWN_SKILLS:
            if skill.lower() in text:
                skills.append(skill)
        
        return skills