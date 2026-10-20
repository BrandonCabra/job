import re
from pathlib import Path

from tools.models import Evaluation, Job

DEFAULT_SKILLS = ["python", "sql", "microsoft fabric", "jira", "etl", "pipelines", "apis rest", "docker"]


def _terms(text: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[a-zA-Z][a-zA-Z0-9+#. ]*", text)}


def evaluate(job: Job, cv_path: str, skills: list[str] | None = None) -> Evaluation:
    cv = Path(cv_path).read_text(encoding="utf-8").lower()
    description = job.description.lower()
    candidates = skills or DEFAULT_SKILLS
    matched = [skill for skill in candidates if skill.lower() in cv and skill.lower() in description]
    required = [skill for skill in candidates if skill.lower() in description]
    missing = [skill for skill in required if skill not in matched]
    score = round((len(matched) / len(required)) * 100) if required else 0
    rationale = f"{len(matched)} de {len(required)} habilidades detectadas en CV y oferta."
    return Evaluation(score=score, matched_skills=matched, missing_skills=missing, rationale=rationale)
