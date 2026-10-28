import csv
import json
from pathlib import Path

from tools.models import Job


def load_linkedin_import(path: str | Path, limit: int = 50) -> list[Job]:
    """Import user-exported/copy-pasted listings; does not automate LinkedIn access."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"No existe LINKEDIN_IMPORT_PATH: {source}")
    if source.suffix.lower() == ".json":
        records = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(records, dict):
            records = records.get("jobs", [])
    else:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            records = list(csv.DictReader(handle))
    jobs = []
    for record in records[:limit]:
        jobs.append(Job(
            title=(record.get("title") or record.get("job_title") or "").strip(),
            company=(record.get("company") or record.get("employer_name") or "").strip(),
            description=(record.get("description") or record.get("job_description") or "").strip(),
            url=(record.get("url") or record.get("job_url") or "").strip(),
            location=(record.get("location") or "").strip(),
            source="linkedin-import",
            external_id=str(record.get("external_id") or ""),
            published_at=str(record.get("published_at") or ""),
        ))
    return [job for job in jobs if job.title]
