import csv
from pathlib import Path

from tools.models import ApplicationRecord

FIELDS = ["timestamp", "company", "title", "score", "status", "step", "url", "cv_path", "cover_letter_path", "details"]


def log_application(record: ApplicationRecord, path: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    exists = destination.exists()
    with destination.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "company": record.job.company,
            "title": record.job.title,
            "score": record.score,
            "status": record.status,
            "step": record.step,
            "url": record.job.url,
            "cv_path": record.cv_path,
            "cover_letter_path": record.cover_letter_path,
            "details": "; ".join(f"{key}={value}" for key, value in record.details.items()),
        })
