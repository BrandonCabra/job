import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path

from tools.models import ApplicationRecord

FIELDS = [
    "timestamp", "company", "title", "score", "status", "step", "url",
    "cv_path", "cover_letter_path", "pdf_path", "source_cv_path",
    "pdf_url", "source_cv_sha256", "pdf_sha256", "details",
]


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


def log_application(record: ApplicationRecord, path: str) -> None:
    audit = _audit_fields(record)
    record.details.update(audit)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    exists = destination.exists()
    with destination.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
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
