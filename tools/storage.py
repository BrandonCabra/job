import sqlite3
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

from tools.models import Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    external_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    description TEXT NOT NULL,
    url TEXT NOT NULL,
    location TEXT NOT NULL,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(external_id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    matched_skills TEXT NOT NULL,
    missing_skills TEXT NOT NULL,
    rationale TEXT NOT NULL,
    selected_cv_path TEXT NOT NULL,
    selection_method TEXT NOT NULL,
    selection_confidence REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(external_id),
    score INTEGER NOT NULL,
    status TEXT NOT NULL,
    step TEXT NOT NULL,
    cv_path TEXT NOT NULL DEFAULT '',
    cover_letter_path TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(external_id),
    cv_path TEXT NOT NULL,
    cover_letter_path TEXT NOT NULL,
    pdf_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    job_id TEXT REFERENCES jobs(external_id),
    status TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT
);
"""


def _row(job: Job) -> tuple[str, ...]:
    return (
        job.external_id or f"{job.url}|{job.title}|{job.company}",
        job.title, job.company, job.description, job.url, job.location,
        job.source, job.published_at, job.scraped_at, job.status,
    )


def open_database(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SCHEMA)
    return connection


def save_jobs(path: str | Path, jobs: Iterable[Job], limit: int = 50) -> None:
    with open_database(path) as connection:
        connection.executemany(
            """INSERT INTO jobs
            (external_id, title, company, description, url, location, source,
             published_at, scraped_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(external_id) DO UPDATE SET
              description=excluded.description,
              scraped_at=excluded.scraped_at""",
            [_row(job) for job in list(jobs)[:limit]],
        )


def load_jobs(path: str | Path, limit: int = 50) -> list[Job]:
    with open_database(path) as connection:
        rows = connection.execute(
            """SELECT title, company, description, url, location, source,
                      external_id, published_at, scraped_at, status
               FROM jobs ORDER BY scraped_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [Job(*row) for row in rows]


def get_job(path: str | Path, external_id: str) -> Job | None:
    with open_database(path) as connection:
        row = connection.execute(
            """SELECT title, company, description, url, location, source,
                      external_id, published_at, scraped_at, status
               FROM jobs WHERE external_id = ?""",
            (external_id,),
        ).fetchone()
    return Job(*tuple(row)) if row else None


def save_evaluation(path: str | Path, job_id: str, evaluation) -> None:
    import json

    with open_database(path) as connection:
        connection.execute(
            """INSERT INTO evaluations
               (job_id, score, matched_skills, missing_skills, rationale,
                selected_cv_path, selection_method, selection_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(job_id) DO UPDATE SET
                 score=excluded.score, matched_skills=excluded.matched_skills,
                 missing_skills=excluded.missing_skills, rationale=excluded.rationale,
                 selected_cv_path=excluded.selected_cv_path,
                 selection_method=excluded.selection_method,
                 selection_confidence=excluded.selection_confidence,
                 created_at=CURRENT_TIMESTAMP""",
            (
                job_id,
                evaluation.score,
                json.dumps(evaluation.matched_skills, ensure_ascii=False),
                json.dumps(evaluation.missing_skills, ensure_ascii=False),
                evaluation.rationale,
                evaluation.selected_cv_path,
                evaluation.selection_method,
                evaluation.selection_confidence,
            ),
        )


def save_application(path: str | Path, record) -> int:
    import json

    with open_database(path) as connection:
        cursor = connection.execute(
            """INSERT INTO applications
               (job_id, score, status, step, cv_path, cover_letter_path, details)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                record.job.external_id,
                record.score,
                record.status,
                record.step,
                record.cv_path,
                record.cover_letter_path,
                json.dumps(record.details, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def load_applications(path: str | Path) -> list[sqlite3.Row]:
    with open_database(path) as connection:
        return connection.execute(
            """SELECT a.id, a.created_at, a.job_id, j.company, j.title, j.url,
                      a.score, a.status, a.step, a.cv_path, a.cover_letter_path,
                      a.details
               FROM applications a
               JOIN jobs j ON j.external_id = a.job_id
               ORDER BY a.created_at DESC, a.id DESC"""
        ).fetchall()


def get_application(path: str | Path, application_id: int) -> sqlite3.Row | None:
    with open_database(path) as connection:
        return connection.execute(
            """SELECT a.id, a.created_at, a.job_id, j.company, j.title, j.url,
                      a.score, a.status, a.step, a.cv_path, a.cover_letter_path,
                      a.details
               FROM applications a
               JOIN jobs j ON j.external_id = a.job_id
               WHERE a.id = ?""",
            (application_id,),
        ).fetchone()


def update_application_status(
    path: str | Path,
    application_id: int,
    status: str,
    step: str | None = None,
) -> sqlite3.Row | None:
    with open_database(path) as connection:
        current = connection.execute(
            "SELECT step FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        if current is None:
            return None
        connection.execute(
            """UPDATE applications
               SET status = ?, step = ?
               WHERE id = ?""",
            (status, step or current["step"], application_id),
        )
    return get_application(path, application_id)


def create_task(path: str | Path, task_id: str, task_type: str, job_id: str) -> None:
    with open_database(path) as connection:
        connection.execute(
            """INSERT INTO tasks (id, task_type, job_id, status)
               VALUES (?, ?, ?, 'queued')""",
            (task_id, task_type, job_id),
        )


def update_task(
    path: str | Path,
    task_id: str,
    status: str,
    *,
    result: dict | None = None,
    error: str = "",
) -> sqlite3.Row | None:
    import json

    with open_database(path) as connection:
        current = connection.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if current is None:
            return None
        if status == "running":
            connection.execute(
                """UPDATE tasks SET status = ?, started_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, task_id),
            )
        elif status in {"completed", "failed"}:
            connection.execute(
                """UPDATE tasks
                   SET status = ?, result = ?, error = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, json.dumps(result or {}, ensure_ascii=False), error, task_id),
            )
        else:
            connection.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
    return get_task(path, task_id)


def get_task(path: str | Path, task_id: str) -> sqlite3.Row | None:
    with open_database(path) as connection:
        return connection.execute(
            """SELECT id, task_type, job_id, status, result, error,
                      created_at, started_at, completed_at
               FROM tasks WHERE id = ?""",
            (task_id,),
        ).fetchone()


def load_tasks(path: str | Path, limit: int = 50) -> list[sqlite3.Row]:
    with open_database(path) as connection:
        return connection.execute(
            """SELECT id, task_type, job_id, status, result, error,
                      created_at, started_at, completed_at
               FROM tasks ORDER BY created_at DESC LIMIT ?""",
            (max(1, min(limit, 100)),),
        ).fetchall()


def migrate_csv(csv_path: str | Path, database_path: str | Path) -> int:
    source = Path(csv_path)
    if not source.exists():
        return 0
    with open_database(database_path) as connection:
        existing = connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        if existing:
            return 0
        rows = list(csv.DictReader(source.open(newline="", encoding="utf-8")))
        imported = 0
        for row in rows:
            job = connection.execute(
                """SELECT external_id FROM jobs
                   WHERE url = ? OR (company = ? AND title = ?)
                   ORDER BY scraped_at DESC LIMIT 1""",
                (row.get("url", ""), row.get("company", ""), row.get("title", "")),
            ).fetchone()
            if job is None:
                identity = f"{row.get('url', '')}|{row.get('title', '')}|{row.get('company', '')}"
                job_id = hashlib.sha256(identity.lower().encode("utf-8")).hexdigest()[:16]
                connection.execute(
                    """INSERT OR IGNORE INTO jobs
                       (external_id, title, company, description, url, location, source,
                        published_at, scraped_at, status)
                       VALUES (?, ?, ?, '', ?, '', 'legacy-csv', ?, ?, ?)""",
                    (
                        job_id,
                        row.get("title", ""),
                        row.get("company", ""),
                        row.get("url", ""),
                        row.get("timestamp", ""),
                        row.get("timestamp", ""),
                        row.get("status", "legacy"),
                    ),
                )
                job_id = job_id
            else:
                job_id = job["external_id"]
            details = {"legacy_details": row.get("details", "")}
            for key in ("pdf_path", "source_cv_path", "pdf_url", "source_cv_sha256", "pdf_sha256"):
                if row.get(key):
                    details[key] = row[key]
            connection.execute(
                """INSERT INTO applications
                   (job_id, score, status, step, cv_path, cover_letter_path, details, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    int(row.get("score") or 0),
                    row.get("status", "legacy"),
                    row.get("step", "legacy"),
                    row.get("cv_path", ""),
                    row.get("cover_letter_path", ""),
                    json.dumps(details, ensure_ascii=False),
                    row.get("timestamp") or None,
                ),
            )
            imported += 1
        return imported


def save_documents(path: str | Path, job_id: str, cv_path: str, letter_path: str) -> int:
    with open_database(path) as connection:
        cursor = connection.execute(
            """INSERT INTO documents (job_id, cv_path, cover_letter_path, pdf_path)
               VALUES (?, ?, ?, ?)""",
            (job_id, cv_path, letter_path, str(Path(cv_path).with_suffix(".pdf"))),
        )
        return int(cursor.lastrowid)


def migrate_json(json_path: str | Path, database_path: str | Path) -> int:
    from tools.scraper import load_local_jobs

    source = Path(json_path)
    if not source.exists():
        return 0
    jobs = load_local_jobs(source)
    save_jobs(database_path, jobs)
    return len(jobs)
