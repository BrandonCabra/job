import json
import logging
import os
import re
from pathlib import Path

from tools.models import Evaluation, Job
from tools.llm_safety import SYSTEM_PROMPT, ensure_llm_endpoint_allowed, untrusted_offer, llm_host

logger = logging.getLogger(__name__)

DEFAULT_SKILLS = [
    "python",
    "sql",
    "microsoft fabric",
    "jira",
    "etl",
    "pipelines",
    "apis rest",
    "docker",
    "aws",
    "azure",
    "ci/cd",
    "github actions",
    "java",
    "javascript",
    "mysql",
    "pruebas funcionales",
    "pruebas exploratorias",
]
DEFAULT_OLLAMA_MODEL = "llama3.2"


def _terms(text: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[a-zA-Z][a-zA-Z0-9+#. ]*", text)}


def _candidate_catalog(cv_dir: Path) -> list[dict[str, str]]:
    catalog = []
    for path in sorted(cv_dir.glob("*.md")):
        if path.name == "master_cv.md":
            continue
        content = path.read_text(encoding="utf-8")
        content_lower = content.lower()
        skills = [skill for skill in DEFAULT_SKILLS if skill in content_lower]
        heading = next((line.strip() for line in content.splitlines() if line.strip()), path.stem)
        catalog.append({"filename": path.name, "profile": f"{heading[:180]}\nHabilidades: {', '.join(skills)}"})
    return catalog


def _local_selection(description: str, catalog: list[dict[str, str]]) -> tuple[str, float]:
    description_lower = description.lower()
    relevant_skills = [skill for skill in DEFAULT_SKILLS if skill in description_lower]
    if not relevant_skills:
        relevant_skills = list(set(re.findall(r"[a-z0-9+#.]+", description_lower)))
    profile_terms = {
        "data": ("data engineer", "data"),
        "qa": ("qa", "quality", "testing", "test"),
        "devops": ("devops", "cloud"),
        "cloud": ("cloud", "aws", "azure"),
        "full": ("full stack", "full-stack"),
        "stack": ("full stack", "full-stack"),
    }
    ranked = sorted(
        (
            (
                sum(skill in candidate["profile"].lower() for skill in relevant_skills)
                + sum(
                    term in description_lower and keyword in candidate["filename"].lower()
                    for term, keywords in profile_terms.items()
                    for keyword in keywords
                ),
                candidate["filename"],
            )
            for candidate in catalog
        ),
        reverse=True,
    )
    if not ranked:
        raise FileNotFoundError(f"No se encontraron CV .md en {catalog}")
    best_score, filename = ranked[0]
    confidence = round(best_score / max(len(relevant_skills), 1), 2)
    return filename, confidence


def _llm_selection(description: str, catalog: list[dict[str, str]]) -> tuple[str, float]:
    try:
        import ollama
        import httpx
    except ImportError as exc:
        raise RuntimeError("El paquete ollama no está instalado") from exc

    ensure_llm_endpoint_allowed()
    prompt = (
        "Selecciona el CV base más adecuado para esta oferta. "
        "Devuelve únicamente JSON válido con las claves filename y confidence. "
        "filename debe coincidir exactamente con uno de los filenames del catálogo; "
        "confidence debe ser un número entre 0 y 1.\n\n"
        f"{untrusted_offer(description)}\n\nCATÁLOGO:\n{json.dumps(catalog, ensure_ascii=False)}"
    )
    client = ollama.Client(
        host=llm_host(),
        timeout=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90")),
    )
    try:
        response = client.chat(
            model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            messages=[
                {
                    "role": "system",
                    "content": f"Eres un reclutador técnico experto en seleccionar perfiles profesionales. {SYSTEM_PROMPT}",
                },
                {"role": "user", "content": prompt},
            ],
            format="json",
        )
    except (ollama.ResponseError, httpx.TimeoutException, OSError, TimeoutError) as exc:
        raise RuntimeError("No fue posible consultar Ollama") from exc
    raw = response["message"]["content"]
    selection = json.loads(raw)
    filename = selection["filename"]
    confidence = float(selection["confidence"])
    valid_filenames = {candidate["filename"] for candidate in catalog}
    if filename not in valid_filenames or not 0 <= confidence <= 1:
        raise ValueError("La respuesta del LLM no seleccionó un archivo válido")
    return filename, confidence


def _select_cv(job: Job, cv_path: str) -> tuple[str, str, float | None]:
    base_path = Path(cv_path)
    catalog = _candidate_catalog(base_path.parent)
    if not catalog:
        return str(base_path), "configured", None

    selection_text = f"{job.title}\n{job.description}"
    try:
        filename, confidence = _llm_selection(selection_text, catalog)
        return str(base_path.parent / filename), "ollama", confidence
    except (OSError, RuntimeError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Selección Ollama no disponible; se usa fallback local: %s", exc)
        filename, confidence = _local_selection(selection_text, catalog)
        return str(base_path.parent / filename), "local-fallback", confidence


def evaluate(job: Job, cv_path: str, skills: list[str] | None = None) -> Evaluation:
    selected_cv_path, selection_method, selection_confidence = _select_cv(job, cv_path)
    cv = Path(selected_cv_path).read_text(encoding="utf-8").lower()
    description = job.description.lower()
    candidates = skills or DEFAULT_SKILLS
    matched = [skill for skill in candidates if skill.lower() in cv and skill.lower() in description]
    required = [skill for skill in candidates if skill.lower() in description]
    missing = [skill for skill in required if skill not in matched]
    score = round((len(matched) / len(required)) * 100) if required else 0
    rationale = (
        f"{len(matched)} de {len(required)} habilidades detectadas en CV y oferta. "
        f"CV seleccionado mediante {selection_method}: {Path(selected_cv_path).name}."
    )
    return Evaluation(
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        rationale=rationale,
        selected_cv_path=selected_cv_path,
        selection_method=selection_method,
        selection_confidence=selection_confidence,
    )
