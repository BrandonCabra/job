import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None

from tools.browser_agent import prepare_submission
from tools.crm_logger import log_application
from tools.evaluator import evaluate
from tools.generator import generate_documents
from tools.models import ApplicationRecord
from tools.scraper import search_jobs


def run() -> None:
    load_dotenv()
    root = Path(__file__).parent
    source = os.getenv("JOB_SOURCE", "local")
    threshold = int(os.getenv("MIN_COMPATIBILITY", "70"))
    cv_path = str(root / "data" / "master_cv.md")
    crm_path = os.getenv("CRM_PATH", str(root / "data" / "applications.csv"))
    jobs = search_jobs(source, str(root / "data" / "jobs.json"), os.getenv("JSEARCH_QUERY", ""), os.getenv("JSEARCH_LOCATION", ""))

    for job in jobs:
        evaluation = evaluate(job, cv_path)
        base = {"matched": evaluation.matched_skills, "missing": evaluation.missing_skills, "rationale": evaluation.rationale}
        if evaluation.score < threshold:
            record = ApplicationRecord(job, evaluation.score, "Omitida", "Evaluación", details=base)
        else:
            cv, letter = generate_documents(job, cv_path, evaluation, str(root / "output"))
            status, step = prepare_submission(job, cv, letter, os.getenv("AUTO_SUBMIT", "false").lower() == "true")
            record = ApplicationRecord(job, evaluation.score, status, step, cv, letter, base)
        log_application(record, crm_path)
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
