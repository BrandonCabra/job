import json
import os
from typing import Any

import requests

from tools.models import Job


def _value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _records(payload: Any, response_path: str) -> list[dict[str, Any]]:
    value = payload
    for part in response_path.split("."):
        if part:
            if not isinstance(value, dict):
                return []
            value = value.get(part)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def search_rapidapi_jobs(
    prefix: str,
    queries: list[str],
    location: str,
    limit: int,
) -> list[Job]:
    host = os.getenv(f"{prefix}_RAPIDAPI_HOST", "").strip()
    endpoint = os.getenv(f"{prefix}_RAPIDAPI_ENDPOINT", "").strip("/")
    api_key = os.getenv("JSEARCH_API_KEY", "").strip()
    if not host or not endpoint:
        print(f"{prefix} omitido: define host y endpoint de RapidAPI.")
        return []
    if not api_key:
        raise RuntimeError("Falta JSEARCH_API_KEY para las fuentes RapidAPI.")
    try:
        static_params = json.loads(os.getenv(f"{prefix}_RAPIDAPI_PARAMS_JSON", "{}"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{prefix}_RAPIDAPI_PARAMS_JSON no es JSON válido") from exc
    query_param = os.getenv(f"{prefix}_RAPIDAPI_QUERY_PARAM", "query")
    response_path = os.getenv(f"{prefix}_RAPIDAPI_RESPONSE_PATH", "data")
    jobs: list[Job] = []
    per_query = max(1, (limit + len(queries) - 1) // len(queries))
    for query in queries:
        params = dict(static_params)
        params[query_param] = f"{query} {location}".strip()
        response = requests.get(
            f"https://{host}/{endpoint}",
            params=params,
            headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(f"{prefix} respondió HTTP {response.status_code}: {response.text[:300]}")
        for item in _records(response.json(), response_path)[:per_query]:
            title = _value(item, "title", "job_title", "name")
            if not title:
                continue
            jobs.append(Job(
                title=title,
                company=_value(item, "company", "company_name", "employer_name") or "Empresa desconocida",
                description=_value(item, "description", "job_description", "snippet"),
                url=_value(item, "url", "job_url", "apply_url", "link"),
                location=_value(item, "location", "job_location", "city"),
                source=prefix.lower(),
                external_id=_value(item, "id", "job_id", "external_id"),
                published_at=_value(item, "published_at", "date_posted", "created_at"),
            ))
        if len(jobs) >= limit:
            break
    return jobs[:limit]
