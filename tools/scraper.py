import hashlib
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from tools.models import Job

DEFAULT_ROLE_QUERIES = [
    "Data Engineer",
    "Ingeniero de Datos",
    "QA Tester",
    "Analista QA",
    "DevOps Engineer",
    "Ingeniero DevOps",
    "Cloud Engineer",
    "Ingeniero Cloud",
    "Full Stack Developer",
    "Desarrollador Full Stack",
    "Software Developer",
    "Desarrollador de Software",
    "Software Programmer",
    "Programador de Software",
]
DEFAULT_MAX_JOBS = 50
SENIORITY_EXCLUSIONS = (
    "senior",
    "sr.",
    "sr ",
    "mid-senior",
    "lead",
    "principal",
    "staff",
    "manager",
    "director",
    "architect",
    "arquitecto",
    "jefe",
    "gerente",
    "lider",
    "líder",
    "senior",
)

COUNTRY_LOCATIONS = {
    "co": ("colombia", "bogotá", "bogota", "medellín", "medellin", "cali", "barranquilla"),
    "es": ("spain", "españa", "madrid", "barcelona", "valencia", "sevilla"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_id(url: str, title: str, company: str) -> str:
    identity = url.strip() or f"{title}|{company}"
    return hashlib.sha256(identity.lower().encode("utf-8")).hexdigest()[:16]


def _job_from_record(record: dict) -> Job:
    allowed = {field for field in Job.__dataclass_fields__}
    return Job(**{key: value for key, value in record.items() if key in allowed})


def load_local_jobs(path: str | Path) -> list[Job]:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = records.get("jobs", [])
    return [_job_from_record(record) for record in records]


def save_jobs(path: str | Path, jobs: Iterable[Job]) -> None:
    records = [
        {
            key: value
            for key, value in job.__dict__.items()
            if value not in ("", None)
        }
        for job in jobs
    ]
    Path(path).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_job(item: dict, source: str, scraped_at: str) -> Job:
    title = (item.get("job_title") or item.get("title") or "Sin título").strip()
    company = (item.get("employer_name") or item.get("company") or "Empresa desconocida").strip()
    url = (item.get("job_apply_link") or item.get("job_url") or item.get("url") or "").strip()
    return Job(
        title=title,
        company=company,
        description=(item.get("job_description") or item.get("description") or "").strip(),
        url=url,
        location=(item.get("job_location") or item.get("location") or "").strip(),
        source=source,
        external_id=str(item.get("job_id") or _job_id(url, title, company)),
        published_at=str(item.get("job_posted_at_datetime_utc") or item.get("published_at") or ""),
        scraped_at=scraped_at,
    )


def _matches_jsearch_preferences(item: dict, country: str) -> bool:
    target_country = country.strip().lower()
    location = " ".join(
        str(item.get(key) or "")
        for key in ("job_location", "location", "job_city", "job_state", "job_country")
    ).lower()
    provider_country = str(item.get("job_country") or "").strip().lower()
    country_aliases = {
        "co": ("co", "colombia", "colomb"),
        "es": ("es", "spain", "españa", "spanish"),
    }
    aliases = country_aliases.get(target_country, (target_country,))
    if provider_country and not any(alias == provider_country or alias in provider_country for alias in aliases):
        return False
    if any(marker in location for marker in ("spain", "españa", "madrid", "barcelona", "valencia")) and target_country == "co":
        return False
    title_description = " ".join(
        str(item.get(key) or "") for key in ("job_title", "title", "job_description", "description")
    ).lower()
    exclusions = tuple(
        item.strip().lower()
        for item in os.getenv("JSEARCH_EXCLUDE_SENIORITY", ",".join(SENIORITY_EXCLUSIONS)).split(",")
        if item.strip()
    )
    return not any(marker in f" {title_description} " for marker in exclusions)


def search_jsearch(query: str, location: str = "", limit: int = 10) -> list[Job]:
    api_key = os.getenv("JSEARCH_API_KEY")
    if not api_key:
        raise RuntimeError("Falta JSEARCH_API_KEY para usar JSearch")
    import requests

    rapidapi_host = os.getenv("JSEARCH_HOST", "jsearch-mega.p.rapidapi.com")
    endpoint = os.getenv("JSEARCH_ENDPOINT", "search").strip("/")
    country = os.getenv("JSEARCH_COUNTRY", "us")
    date_posted = os.getenv("JSEARCH_DATE_POSTED", "all")
    language = os.getenv("JSEARCH_LANGUAGE", "en")
    normalized_location = location.strip()
    expected_locations = COUNTRY_LOCATIONS.get(country.strip().lower(), ())
    if normalized_location and expected_locations and not any(
        marker in normalized_location.lower() for marker in expected_locations
    ):
        print(
            f"Ubicación incompatible ({normalized_location!r}) con "
            f"JSEARCH_COUNTRY={country!r}; se usará la ubicación del país configurado."
        )
        normalized_location = "Colombia" if country.strip().lower() == "co" else country
    query_suffix = os.getenv("JSEARCH_QUERY_SUFFIX", "").strip()
    effective_query = f"{query} {query_suffix} {normalized_location}".strip()
    response = requests.get(
        f"https://{rapidapi_host}/{endpoint}",
        params={
            "query": effective_query,
            "page": "1",
            "num_pages": "1",
            "country": country,
            "date_posted": date_posted,
            "language": language,
        },
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": rapidapi_host},
        timeout=30,
    )
    if not response.ok:
        try:
            detail = response.json().get("message", response.text[:300])
        except ValueError:
            detail = response.text[:300]
        raise RuntimeError(
            f"JSearch respondió HTTP {response.status_code}: {detail}. "
            f"Verifica JSEARCH_HOST y la suscripción al API en RapidAPI."
        )
    data = response.json().get("data", [])
    if not data:
        print(
            f"JSearch no devolvió resultados para query={query!r}, "
            f"location={location!r}, country={country!r}. "
            "Prueba otra consulta o confirma la cobertura geográfica de tu suscripción."
        )
    scraped_at = _now()
    filtered = [item for item in data if _matches_jsearch_preferences(item, country)]
    return [_normalize_job(item, "jsearch", scraped_at) for item in filtered[:limit]]


def search_jsearch_queries(queries: list[str], location: str, limit: int) -> list[Job]:
    jobs: list[Job] = []
    per_query = max(1, (limit + len(queries) - 1) // len(queries))
    for query in queries:
        jobs.extend(search_jsearch(query, location, per_query))
    return _deduplicate(jobs)[:limit]


def search_rss(feed_urls: list[str], limit: int = DEFAULT_MAX_JOBS) -> list[Job]:
    jobs: list[Job] = []
    for feed_url in feed_urls:
        with urllib.request.urlopen(feed_url, timeout=30) as response:
            root = ET.fromstring(response.read())
        for item in root.findall(".//item") + root.findall(".//{*}entry"):
            def text(*names: str) -> str:
                for name in names:
                    node = item.find(name)
                    if node is None:
                        node = item.find(f"{{*}}{name}")
                    if node is not None and node.text:
                        return node.text.strip()
                return ""

            link_node = item.find("link")
            if link_node is None:
                link_node = item.find("{*}link")
            link = (link_node.text or "").strip() if link_node is not None else ""
            jobs.append(_normalize_job({
                "title": text("title"),
                "description": text("description", "summary"),
                "url": link,
                "company": text("author", "creator"),
                "published_at": text("pubDate", "published", "updated"),
            }, "rss", _now()))
            if len(jobs) >= limit:
                return _deduplicate(jobs)[:limit]
    return _deduplicate(jobs)[:limit]


def _deduplicate(jobs: Iterable[Job]) -> list[Job]:
    unique: dict[str, Job] = {}
    for job in jobs:
        key = job.external_id or _job_id(job.url, job.title, job.company)
        if key not in unique or len(job.description) > len(unique[key].description):
            unique[key] = job
    return list(unique.values())


def merge_jobs(existing: Iterable[Job], incoming: Iterable[Job], limit: int = DEFAULT_MAX_JOBS) -> list[Job]:
    merged = {job.external_id or _job_id(job.url, job.title, job.company): job for job in existing}
    for job in incoming:
        key = job.external_id or _job_id(job.url, job.title, job.company)
        if key not in merged:
            merged[key] = job
    return list(merged.values())[:limit]


def fetch_and_store(
    path: str | Path,
    queries: list[str],
    location: str = "",
    limit: int = DEFAULT_MAX_JOBS,
    rss_feeds: list[str] | None = None,
) -> list[Job]:
    existing = load_local_jobs(path) if Path(path).exists() else []
    configured_sources = [
        item.strip().lower()
        for item in os.getenv("JOB_SOURCES", "jsearch,rss").split(",")
        if item.strip()
    ]
    incoming: list[Job] = []
    source_errors: list[str] = []

    def collect(source: str, loader: Callable[[int], list[Job]]) -> None:
        try:
            remaining = max(0, limit - len(incoming))
            if remaining:
                incoming.extend(loader(remaining))
        except (RuntimeError, OSError, ValueError) as exc:
            source_errors.append(f"{source}: {exc}")
            print(f"Error en fuente {source}: {exc}")

    if "jsearch" in configured_sources:
        collect("jsearch", lambda remaining: search_jsearch_queries(queries, location, remaining))
    if "computrabajo" in configured_sources:
        from tools.sources.computrabajo import search_computrabajo

        collect(
            "computrabajo",
            lambda remaining: search_computrabajo(
                queries,
                location,
                remaining,
                os.getenv("COMPUTRABAJO_SEARCH_URL_TEMPLATE", ""),
            ),
        )
    if "linkedin-import" in configured_sources:
        from tools.sources.linkedin_import import load_linkedin_import

        import_path = os.getenv("LINKEDIN_IMPORT_PATH", "")
        if import_path:
            collect("linkedin-import", lambda remaining: load_linkedin_import(import_path, remaining))
        else:
            print("LinkedIn import omitido: define LINKEDIN_IMPORT_PATH para habilitarlo.")
    for source_name, prefix in (("facebook-api", "FACEBOOK"), ("linkedin-api", "LINKEDIN")):
        if source_name in configured_sources:
            from tools.sources.rapidapi_jobs import search_rapidapi_jobs

            collect(
                source_name,
                lambda remaining, source_prefix=prefix: search_rapidapi_jobs(
                    source_prefix, queries, location, remaining
                ),
            )
    if rss_feeds and "rss" in configured_sources:
        collect("rss", lambda remaining: search_rss(rss_feeds, remaining))
    if source_errors:
        print(f"Fuentes con error: {len(source_errors)}; se conservarán las demás fuentes.")
    if os.getenv("JSEARCH_CLEAN_CATALOG", "false").lower() == "true" and "jsearch" in configured_sources:
        country = os.getenv("JSEARCH_COUNTRY", "us")
        before = len(existing)
        existing = [
            job for job in existing
            if job.source != "jsearch"
            or _matches_jsearch_preferences(
                {
                    "title": job.title,
                    "description": job.description,
                    "location": job.location,
                },
                country,
            )
        ]
        print(f"Catálogo JSearch filtrado: {before - len(existing)} ofertas descartadas.")
    existing_ids = {
        job.external_id or _job_id(job.url, job.title, job.company)
        for job in existing
    }
    merged = merge_jobs(existing, incoming, limit)
    save_jobs(path, merged)
    return [
        job for job in incoming
        if (job.external_id or _job_id(job.url, job.title, job.company)) not in existing_ids
    ][:limit]


def search_jobs(source: str, local_path: str, query: str, location: str) -> Iterable[Job]:
    if source == "jsearch":
        queries = [item.strip() for item in os.getenv("JSEARCH_QUERIES", "").split(",") if item.strip()]
        queries = queries or ([query] if query else DEFAULT_ROLE_QUERIES)
        limit = min(int(os.getenv("MAX_OLLAMA_JOBS", str(DEFAULT_MAX_JOBS))), DEFAULT_MAX_JOBS)
        return search_jsearch_queries(queries, location, limit)
    return load_local_jobs(local_path)
