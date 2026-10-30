import json
import os
from pathlib import Path

from tools.browser_agent import prepare_submission
from tools.crm_logger import log_application
from tools.evaluator import evaluate
from tools.generator import generate_documents
from tools.models import ApplicationRecord
from tools.services.job_service import JobService
from tools.scraper import search_jobs


def run(jobs_override=None) -> None:
    root = Path(__file__).parent
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip():
                os.environ[key.strip()] = value.strip().strip("\"'")
    source = os.getenv("JOB_SOURCE", "local")
    threshold = int(os.getenv("MIN_COMPATIBILITY", "70"))
    cv_path = os.getenv("CV_PATH", str(root / "data" / "master_cv.md"))
    if not os.path.isabs(cv_path):
        cv_path = str(root / cv_path)
    crm_path = os.getenv("CRM_PATH", str(root / "data" / "applications.csv"))
    database_path = None
    if os.getenv("STORAGE_BACKEND", "json").lower() == "sqlite":
        configured_database = Path(os.getenv("JOB_DB_PATH", "data/jobs.db"))
        database_path = str(configured_database if configured_database.is_absolute() else root / configured_database)
        from tools.storage import migrate_csv

        migrate_csv(crm_path, database_path)
    max_jobs = min(int(os.getenv("MAX_OLLAMA_JOBS", "50")), 50)
    service = JobService(
        root,
        evaluator=evaluate,
        document_generator=generate_documents,
        persist=os.getenv("STORAGE_BACKEND", "json").lower() == "sqlite",
    )
    if jobs_override is not None:
        jobs = list(jobs_override)[:max_jobs]
    elif os.getenv("STORAGE_BACKEND", "json").lower() == "sqlite" and source == "local":
        from tools.storage import load_jobs

        database = root / os.getenv("JOB_DB_PATH", "data/jobs.db")
        if not database.is_absolute():
            database = root / database
        jobs = load_jobs(database, max_jobs)
    else:
        jobs = list(search_jobs(
            source,
            str(root / "data" / "jobs.json"),
            os.getenv("JSEARCH_QUERY", ""),
            os.getenv("JSEARCH_LOCATION", ""),
        ))[:max_jobs]

    for job in jobs:
        service.cv_path = Path(cv_path)
        evaluation = service.evaluate(job)
        base = {
            "matched": evaluation.matched_skills,
            "missing": evaluation.missing_skills,
            "rationale": evaluation.rationale,
            "selected_cv": evaluation.selected_cv_path,
            "selection_method": evaluation.selection_method,
            "selection_confidence": evaluation.selection_confidence,
        }
        if evaluation.score < threshold:
            record = ApplicationRecord(job, evaluation.score, "Omitida", "Evaluación", details=base)
        else:
            cv, letter = service.generate_documents(job, evaluation)
            pdf_path = str(Path(cv).with_suffix(".pdf"))
            base["pdf_path"] = pdf_path
            status, step = prepare_submission(job, cv, letter, os.getenv("AUTO_SUBMIT", "false").lower() == "true")
            record = ApplicationRecord(job, evaluation.score, status, step, cv, letter, base)
        log_application(record, crm_path, database_path)
        print(json.dumps({
            "paso": record.step,
            "empresa": job.company,
            "puesto": job.title,
            "compatibilidad": evaluation.score,
            "estado": record.status,
            "url": job.url,
            "detalles": record.details,
        }, ensure_ascii=False))


if __name__ == "__main__":
    run()
