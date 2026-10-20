import re
from pathlib import Path

from tools.models import Evaluation, Job


def _experience_lines(cv: str, matched: list[str]) -> list[str]:
    lines = [line.strip() for line in cv.splitlines() if line.strip().startswith("-")]
    keywords = [skill.lower() for skill in matched]
    relevant = [line for line in lines if any(keyword in line.lower() for keyword in keywords)]
    return relevant or lines[:5]


def generate_documents(job: Job, cv_path: str, evaluation: Evaluation, output_dir: str) -> tuple[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{job.company}-{job.title}".lower()).strip("-")
    cv = Path(cv_path).read_text(encoding="utf-8")
    bullets = _experience_lines(cv, evaluation.matched_skills)
    adapted_cv = destination / f"{slug}-cv.md"
    adapted_cv.write_text(
        f"# CV adaptado | {job.title} en {job.company}\n\n"
        f"## Habilidades relevantes\n{', '.join(evaluation.matched_skills)}\n\n"
        "## Experiencia destacada\n" + "\n".join(bullets) + "\n",
        encoding="utf-8",
    )
    letter = destination / f"{slug}-carta.md"
    letter.write_text(
        f"# Carta de presentación\n\nEstimado equipo de {job.company}:\n\n"
        f"Me interesa el puesto de **{job.title}** porque mi experiencia con "
        f"{', '.join(evaluation.matched_skills)} se alinea con las necesidades descritas. "
        "Puedo aportar una forma de trabajo orientada a la calidad, la automatización y la colaboración.\n\n"
        "Quedo a su disposición para conversar sobre cómo puedo contribuir al equipo.\n\nAtentamente,\nNombre Apellido\n",
        encoding="utf-8",
    )
    return str(adapted_cv), str(letter)
