import os
from pathlib import Path

from tools.evaluator import evaluate
from tools.generator import generate_documents
from tools.models import Evaluation, Job
from tools.storage import get_job, save_documents, save_evaluation, save_jobs


class JobService:
    def __init__(
        self,
        root: str | Path,
        evaluator=evaluate,
        document_generator=generate_documents,
        persist: bool = True,
    ):
        self.root = Path(root)
        self._evaluator = evaluator
        self._document_generator = document_generator
        self.persist = persist
        self.database = self._configured_path("JOB_DB_PATH", "data/jobs.db")
        self.cv_path = self._configured_path("CV_PATH", "data/master_cv.md")
        self.output_dir = self.root / "output"

    def _configured_path(self, name: str, default: str) -> Path:
        configured = Path(os.getenv(name, default))
        return configured if configured.is_absolute() else self.root / configured

    def find(self, job_id: str) -> Job | None:
        return get_job(self.database, job_id)

    def evaluate(self, job: Job) -> Evaluation:
        if self.persist:
            save_jobs(self.database, [job], limit=1)
        result = self._evaluator(job, str(self.cv_path))
        if self.persist:
            save_evaluation(self.database, job.external_id, result)
        return result

    def generate_documents(self, job: Job, evaluation: Evaluation) -> tuple[str, str]:
        cv, letter = self._document_generator(
            job, evaluation.selected_cv_path, evaluation, str(self.output_dir)
        )
        if self.persist:
            save_documents(self.database, job.external_id, cv, letter)
        return cv, letter
