import json
import html
import logging
import os
import re
from pathlib import Path

from tools.models import Evaluation, Job

logger = logging.getLogger(__name__)


def _experience_lines(cv: str, matched: list[str]) -> list[str]:
    lines = [
        line.strip()
        for line in cv.splitlines()
        if re.match(r"^(?:[-*·•])\s+", line.strip())
    ]
    keywords = [skill.lower() for skill in matched]
    relevant = [line for line in lines if any(keyword in line.lower() for keyword in keywords)]
    return relevant or lines[:8]


SECTION_NAMES = (
    "PERFIL PROFESIONAL",
    "EDUCACIÓN",
    "EXPERIENCIA PROFESIONAL",
    "HABILIDADES",
    "CURSOS Y CERTIFICACIONES SELECCIONADOS",
    "IDIOMAS",
)


def _parse_cv(cv: str) -> tuple[list[str], dict[str, list[str]]]:
    lines = [line.rstrip() for line in cv.replace("\f", "").splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    header = [line.strip() for line in lines[:3] if line.strip()]
    sections: dict[str, list[str]] = {}
    current = ""
    for line in lines[3:]:
        candidate = line.strip()
        if candidate.upper() in SECTION_NAMES:
            current = candidate.upper()
            sections[current] = []
        elif current and candidate:
            sections[current].append(candidate)
    return header, sections


def _experience_bullets(lines: list[str]) -> tuple[list[str], list[str]]:
    entries: list[str] = []
    bullets: list[str] = []
    current_bullet = ""
    for line in lines:
        if re.match(r"^(?:[-*·•])\s+", line):
            if current_bullet:
                bullets.append(current_bullet)
            current_bullet = re.sub(r"^(?:[-*·•])\s+", "", line)
        elif current_bullet:
            current_bullet += f" {line}"
        else:
            entries.append(line)
    if current_bullet:
        bullets.append(current_bullet)
    return entries, bullets


def _markdown_section(title: str, lines: list[str]) -> str:
    if title == "EXPERIENCIA PROFESIONAL":
        entries, bullets = _experience_bullets(lines)
        result = [f"## {title.title()}", ""]
        result.extend(entries)
        result.extend(f"· {bullet}" for bullet in bullets)
        return "\n".join(result)
    result = [f"## {title.title()}", ""]
    result.extend(lines)
    return "\n".join(result)


def _experience_html(lines: list[str], bullets: list[str]) -> str:
        result: list[str] = []
        bullet_index = 0
        for line in lines:
            if re.match(r"^(?:[-*·•])\s+", line):
                if bullet_index < len(bullets):
                    result.append(f"<li>{html.escape(bullets[bullet_index])}</li>")
                    bullet_index += 1
            else:
                result.append(f'<div class="experience-heading">{html.escape(line)}</div>')
        return "\n".join(result)


def _html_document(
        job: Job,
        header: list[str],
        sections: dict[str, list[str]],
        original_experience: list[str],
        bullets: list[str],
        evaluation: Evaluation,
) -> str:
        contact = " · ".join(html.escape(line) for line in header[1:])
        name = html.escape(header[0] if header else "Currículum")
        headline = html.escape(header[2] if len(header) > 2 else job.title)
        body: list[str] = []
        body.append(f'<header><h1>{name}</h1><div class="headline">{headline}</div><div class="contact">{contact}</div></header>')
        body.append('<section><h2>Perfil profesional</h2><p>' + html.escape(" ".join(sections.get("PERFIL PROFESIONAL", []))) + "</p></section>")
        body.append(
            '<section><h2>Habilidades relevantes</h2><p class="keyword-list">'
            + html.escape(", ".join(evaluation.matched_skills) or "Ninguna detectada")
            + "</p></section>"
        )
        for title in SECTION_NAMES:
            if title in {"PERFIL PROFESIONAL"} or title not in sections:
                continue
            if title == "EXPERIENCIA PROFESIONAL":
                content = _experience_html(sections[title], bullets)
                body.append(f'<section><h2>{html.escape(title.title())}</h2><ul class="experience">{content}</ul></section>')
            else:
                items = []
                for line in sections[title]:
                    escaped = html.escape(line)
                    if re.match(r"^(?:[-*·•])\s+", line):
                        escaped = re.sub(r"^(?:[-*·•])\s+", "", escaped)
                        items.append(f"<li>{escaped}</li>")
                    else:
                        items.append(f"<p>{escaped}</p>")
                body.append(f'<section><h2>{html.escape(title.title())}</h2>{"".join(items)}</section>')
        return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{name} - {html.escape(job.title)}</title>
<style>
@page {{ size: A4; margin: 16mm 17mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{ color: #27313b; font-family: Arial, Helvetica, sans-serif; font-size: 9.5pt; line-height: 1.35; margin: 0; }}
header {{ border-bottom: 2px solid #163a5f; padding-bottom: 10px; margin-bottom: 15px; }}
h1 {{ color: #163a5f; font-size: 22pt; letter-spacing: .3px; margin: 0 0 3px; }}
.headline {{ color: #35678f; font-size: 10.5pt; font-weight: bold; text-transform: uppercase; }}
.contact {{ color: #59636d; font-size: 8.5pt; margin-top: 6px; }}
section {{ margin: 0 0 13px; break-inside: avoid; }}
h2 {{ border-bottom: 1px solid #d6dee6; color: #163a5f; font-size: 10.5pt; letter-spacing: .7px; margin: 0 0 7px; padding-bottom: 3px; text-transform: uppercase; }}
p {{ margin: 0 0 5px; }}
ul {{ margin: 3px 0 0 17px; padding: 0; }}
li {{ margin: 0 0 4px; padding-left: 2px; }}
.keyword-list {{ color: #355b78; font-weight: bold; }}
.experience {{ break-inside: auto; }}
.experience-heading {{ color: #1f2933; font-weight: bold; margin: 7px 0 3px; break-after: avoid; }}
.experience-heading:first-child {{ margin-top: 0; }}
</style>
</head>
<body>{"".join(body)}</body>
</html>"""
def _normalize(text: str) -> set[str]:
    return set(re.findall(r"[a-záéíóúñ0-9+#./-]{3,}", text.lower()))


def _rewrite_bullets(job: Job, cv: str, bullets: list[str], evaluation: Evaluation) -> list[str]:
    try:
        import httpx
        import ollama
    except ImportError:
        return bullets

    evidence = "\n".join(f"{index + 1}. {bullet}" for index, bullet in enumerate(bullets))
    prompt = (
        "Reescribe sutilmente estos bullets de experiencia para adaptar un CV a una oferta. "
        "Devuelve únicamente un JSON con la clave bullets, cuyo valor sea una lista con la misma "
        "cantidad de elementos. Conserva hechos, empresas, herramientas, fechas y alcance. "
        "No inventes logros, métricas, responsabilidades ni tecnologías. Solo puedes usar tecnologías "
        "que aparezcan literalmente en la evidencia. Prioriza las habilidades coincidentes y, si una "
        "habilidad falta, no la agregues.\n\n"
        f"OFERTA:\n{job.title}: {job.description}\n\n"
        f"HABILIDADES COINCIDENTES: {', '.join(evaluation.matched_skills)}\n"
        f"HABILIDADES FALTANTES: {', '.join(evaluation.missing_skills)}\n\n"
        f"EVIDENCIA DEL CV:\n{evidence}"
    )
    try:
        client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            timeout=float(os.getenv("OLLAMA_GENERATOR_TIMEOUT_SECONDS", "30")),
        )
        response = client.chat(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            messages=[
                {
                    "role": "system",
                    "content": "Eres un editor de CV conservador y verificable.",
                },
                {"role": "user", "content": prompt},
            ],
            format="json",
            options={"num_predict": 500},
        )
        rewritten = json.loads(response["message"]["content"])["bullets"]
        if _valid_rewrite(rewritten, bullets, cv):
            return [bullet.strip("· -*") for bullet in rewritten]
    except (ollama.ResponseError, httpx.TimeoutException, OSError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("No se pudo refinar el CV con Ollama; se conservan bullets originales: %s", exc)
    return bullets


def _refine_experience(job: Job, cv: str, bullets: list[str], evaluation: Evaluation) -> list[str]:
    keywords = [skill.lower() for skill in evaluation.matched_skills]
    selected_indexes = [
        index for index, bullet in enumerate(bullets)
        if any(keyword in bullet.lower() for keyword in keywords)
    ]
    if not selected_indexes:
        selected_indexes = list(range(min(8, len(bullets))))
    selected = [bullets[index] for index in selected_indexes]
    refined = _rewrite_bullets(job, cv, selected, evaluation)
    result = list(bullets)
    for index, bullet in zip(selected_indexes, refined):
        result[index] = bullet
    return result


def _rewrite_profile(job: Job, cv: str, profile: list[str], evaluation: Evaluation) -> list[str]:
    if not profile:
        return profile
    try:
        import httpx
        import ollama

        prompt = (
            "Adapta este perfil profesional a la oferta de empleo. Devuelve únicamente JSON con la "
            "clave profile y un texto. Conserva todos los hechos y no inventes tecnologías, métricas, "
            "cargos, empresas ni años. Solo puedes priorizar información que ya aparece en el texto.\n\n"
            f"OFERTA: {job.title}: {job.description}\n"
            f"HABILIDADES COINCIDENTES: {', '.join(evaluation.matched_skills)}\n"
            f"CV FUENTE:\n{' '.join(profile)}"
        )
        client = ollama.Client(
            host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            timeout=float(os.getenv("OLLAMA_GENERATOR_TIMEOUT_SECONDS", "30")),
        )
        response = client.chat(
            model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            messages=[
                {"role": "system", "content": "Eres un editor de CV conservador y verificable."},
                {"role": "user", "content": prompt},
            ],
            format="json",
            options={"num_predict": 300},
        )
        rewritten = json.loads(response["message"]["content"])["profile"]
        if isinstance(rewritten, str) and _valid_rewrite([rewritten], [" ".join(profile)], cv):
            return [rewritten]
    except (ollama.ResponseError, httpx.TimeoutException, OSError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("No se pudo adaptar el perfil con Ollama; se conserva el original: %s", exc)
    return profile


def _valid_rewrite(rewritten: object, original: list[str], cv: str) -> bool:
    if not isinstance(rewritten, list) or len(rewritten) != len(original):
        return False
    source_terms = _normalize(cv)
    for candidate, source in zip(rewritten, original):
        if not isinstance(candidate, str) or not candidate.strip():
            return False
        candidate_terms = _normalize(candidate)
        if not candidate_terms.intersection(_normalize(source)):
            return False
        technical_terms = {
            term for term in candidate_terms
            if term in {"python", "sql", "java", "javascript", "docker", "aws", "azure",
                        "jira", "etl", "pipelines", "pyspark", "mysql", "fabric", "github",
                        "actions", "rest", "api", "cicd", "ci/cd"}
        }
        if not technical_terms.issubset(source_terms):
            return False
    return True


def _write_pdf(html_text: str, markdown_text: str, destination: Path) -> str | None:
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        PlaywrightError = None
        sync_playwright = None

    if sync_playwright is not None:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(html_text, wait_until="networkidle")
                page.pdf(path=str(destination), format="A4", print_background=True)
                browser.close()
            return str(destination)
        except (PlaywrightError, OSError) as exc:
            logger.warning("No se pudo generar PDF con HTML/Playwright; se usa ReportLab: %s", exc)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        return None

    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    story = []
    for line in markdown_text.splitlines():
        if not line.strip():
            story.append(Spacer(1, 0.18 * cm))
        else:
            style = styles["Heading1"] if line.startswith("# ") else styles["Heading2"] if line.startswith("## ") else styles["BodyText"]
            text = re.sub(r"^#{1,2}\s+", "", line).replace("&", "&amp;")
            story.append(Paragraph(text, style))
    document.build(story)
    return str(destination)


def generate_documents(job: Job, cv_path: str, evaluation: Evaluation, output_dir: str) -> tuple[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{job.company}-{job.title}".lower()).strip("-")
    cv = Path(cv_path).read_text(encoding="utf-8")
    header, sections = _parse_cv(cv)
    sections["PERFIL PROFESIONAL"] = _rewrite_profile(
        job,
        cv,
        sections.get("PERFIL PROFESIONAL", []),
        evaluation,
    )
    experience_entries, original_bullets = _experience_bullets(sections.get("EXPERIENCIA PROFESIONAL", []))
    bullets = _refine_experience(job, cv, original_bullets, evaluation)
    sections["EXPERIENCIA PROFESIONAL"] = experience_entries + [f"· {bullet}" for bullet in bullets]
    adapted_text = f"# CV adaptado | {job.title} en {job.company}\n\n"
    adapted_text += "\n".join(header) + "\n\n"
    adapted_text += f"## Habilidades relevantes\n{', '.join(evaluation.matched_skills) or 'Ninguna detectada'}\n\n"
    for title in SECTION_NAMES:
        if title in sections:
            adapted_text += _markdown_section(title, sections[title]) + "\n\n"
    adapted_cv = destination / f"{slug}-cv.md"
    adapted_cv.write_text(adapted_text, encoding="utf-8")
    html_text = _html_document(
        job,
        header,
        sections,
        sections.get("EXPERIENCIA PROFESIONAL", []),
        bullets,
        evaluation,
    )
    (destination / f"{slug}-cv.html").write_text(html_text, encoding="utf-8")
    _write_pdf(html_text, adapted_text, destination / f"{slug}-cv.pdf")

    letter = destination / f"{slug}-carta.md"
    letter.write_text(
        f"# Carta de presentación\n\nEstimado equipo de {job.company}:\n\n"
        f"Me interesa el puesto de **{job.title}** porque mi experiencia con "
        f"{', '.join(evaluation.matched_skills) or 'desarrollo de software'} se alinea con las necesidades descritas. "
        "Puedo aportar una forma de trabajo orientada a la calidad, la automatización y la colaboración.\n\n"
        "Quedo a su disposición para conversar sobre cómo puedo contribuir al equipo.\n\n"
        "Atentamente,\nNombre Apellido\n",
        encoding="utf-8",
    )
    return str(adapted_cv), str(letter)
