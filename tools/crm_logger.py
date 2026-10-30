import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path

try:
    import portalocker
except ModuleNotFoundError:
    portalocker = None
import fcntl
from contextlib import contextmanager

from tools.models import ApplicationRecord
from tools.storage import load_applications, save_application

FIELDS = [
    "timestamp", "company", "title", "score", "status", "step", "url",
    "cv_path", "cover_letter_path", "pdf_path", "source_cv_path",
    "pdf_url", "source_cv_sha256", "pdf_sha256", "details",
]


@contextmanager
def _locked_csv(path: Path):
    if portalocker is not None:
        with portalocker.Lock(path, mode="a", timeout=30, newline="", encoding="utf-8") as handle:
            yield handle
        return
    with path.open("a", newline="", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audit_fields(record: ApplicationRecord) -> dict[str, str]:
    source_cv = str(record.details.get("selected_cv") or "")
    pdf_path = str(record.details.get("pdf_path") or "")
    pdf_url = Path(pdf_path).resolve().as_uri() if pdf_path and Path(pdf_path).is_file() else ""
    return {
        "pdf_path": pdf_path,
        "pdf_url": pdf_url,
        "source_cv_path": source_cv,
        "source_cv_sha256": _sha256(source_cv) if source_cv and Path(source_cv).is_file() else "",
        "pdf_sha256": _sha256(pdf_path) if pdf_path and Path(pdf_path).is_file() else "",
    }


def _csv_row_from_application(row) -> dict[str, str]:
    import json

    details = json.loads(row["details"] or "{}")
    return {
        "timestamp": row["created_at"],
        "company": row["company"],
        "title": row["title"],
        "score": str(row["score"]),
        "status": row["status"],
        "step": row["step"],
        "url": row["url"],
        "cv_path": row["cv_path"],
        "cover_letter_path": row["cover_letter_path"],
        "pdf_path": details.get("pdf_path", ""),
        "source_cv_path": details.get("selected_cv", ""),
        "pdf_url": details.get("pdf_url", ""),
        "source_cv_sha256": details.get("source_cv_sha256", ""),
        "pdf_sha256": details.get("pdf_sha256", ""),
        "details": "; ".join(f"{key}={value}" for key, value in details.items()),
    }


def export_applications_csv(database_path: str, csv_path: str) -> None:
    destination = Path(csv_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = load_applications(database_path)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(_csv_row_from_application(row) for row in rows)


def _notion_property_text(value: str) -> dict:
    return {"rich_text": [{"text": {"content": value[:2000]}}]} if value else {"rich_text": []}


def _sync_notion(record: ApplicationRecord, audit: dict[str, str]) -> None:
    if os.getenv("NOTION_ENABLED", "false").lower() != "true":
        return
    token = os.getenv("NOTION_TOKEN", "").strip()
    database_id = os.getenv("NOTION_DATABASE_ID", "").strip()
    if not token or not database_id:
        raise RuntimeError("NOTION_ENABLED=true requiere NOTION_TOKEN y NOTION_DATABASE_ID")
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Instala requests para sincronizar con Notion") from exc

    pdf_url = audit["pdf_url"]
    properties = {
        "Name": {"title": [{"text": {"content": f"{record.job.company} - {record.job.title}"[:2000]}}]},
        "Empresa": _notion_property_text(record.job.company),
        "Rol": _notion_property_text(record.job.title),
        "Score": {"number": record.score},
        "Estado": _notion_property_text(record.status),
        "PDF": {"url": pdf_url or None},
        "CV base": _notion_property_text(audit["source_cv_path"]),
        "CV SHA256": _notion_property_text(audit["source_cv_sha256"]),
        "PDF SHA256": _notion_property_text(audit["pdf_sha256"]),
        "Oferta": {"url": record.job.url or None},
    }
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": os.getenv("NOTION_VERSION", "2022-06-28"),
            "Content-Type": "application/json",
        },
        json={"parent": {"database_id": database_id}, "properties": properties},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Notion respondió HTTP {response.status_code}: {response.text[:500]}")


def log_application(
    record: ApplicationRecord,
    path: str,
    database_path: str | None = None,
) -> None:
    audit = _audit_fields(record)
    record.details.update(audit)
    if database_path:
        save_application(database_path, record)
        export_applications_csv(database_path, path)
        try:
            _sync_notion(record, audit)
        except (OSError, RuntimeError) as exc:
            print(f"No se pudo sincronizar la auditoría con Notion; SQLite se conservó: {exc}")
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    exists = destination.exists()
    with _locked_csv(destination) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists or destination.stat().st_size == 0:
            writer.writeheader()
        writer.writerow({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "company": record.job.company,
                "title": record.job.title,
                "score": record.score,
                "status": record.status,
                "step": record.step,
                "url": record.job.url,
                "cv_path": record.cv_path,
                "cover_letter_path": record.cover_letter_path,
                **audit,
                "details": "; ".join(f"{key}={value}" for key, value in record.details.items()),
            })
    try:
        _sync_notion(record, audit)
    except (OSError, RuntimeError) as exc:
        print(f"No se pudo sincronizar la auditoría con Notion; el CSV se conservó: {exc}")
