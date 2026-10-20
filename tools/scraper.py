import json
import os
from pathlib import Path
from typing import Iterable

from tools.models import Job


def load_local_jobs(path: str | Path) -> list[Job]:
    """Carga ofertas normalizadas desde JSON para desarrollo reproducible."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Job(source="local", **record) for record in records]


def search_jsearch(query: str, location: str = "", limit: int = 10) -> list[Job]:
    """Adaptador opcional para JSearch; requiere JSEARCH_API_KEY y requests."""
    api_key = os.getenv("JSEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("Falta JSEARCH_API_KEY para usar JSearch")
    import requests

    response = requests.get(
        "https://jsearch.p.rapidapi.com/search",
        params={"query": f"{query} {location}".strip(), "page": "1", "num_pages": "1"},
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
        timeout=30,
    )
    response.raise_for_status()
    jobs: list[Job] = []
    for item in response.json().get("data", [])[:limit]:
        jobs.append(Job(
            title=item.get("job_title", "Sin título"),
            company=item.get("employer_name", "Empresa desconocida"),
            description=item.get("job_description", ""),
            url=item.get("job_apply_link") or item.get("job_url", ""),
            location=item.get("job_location", ""),
            source="jsearch",
        ))
    return jobs


def search_jobs(source: str, local_path: str, query: str, location: str) -> Iterable[Job]:
    if source == "jsearch":
        return search_jsearch(query, location)
    return load_local_jobs(local_path)
